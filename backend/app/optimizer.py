import cv2
import numpy as np


class EdgeOptimizer:
    # __init__ 和 _precompute_gradients 保持不变
    def __init__(self, image_bytes, budget_ratio=0.3, canny_low=50, canny_high=150):
        nparr = np.frombuffer(image_bytes, np.uint8)
        self.original_image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if self.original_image is None:
            raise ValueError("Unable to load image from bytes.")
        self.gray = cv2.cvtColor(self.original_image, cv2.COLOR_BGR2GRAY)
        self.gray = cv2.GaussianBlur(self.gray, (3, 3), 0)
        self.height, self.width = self.gray.shape
        self.budget_ratio = budget_ratio
        self.canny_low = canny_low
        self.canny_high = canny_high
        self._precompute_gradients()
        self.update_canny_edges()

    def update_canny_parameters(self, low_threshold, high_threshold):
        self.canny_low = low_threshold
        self.canny_high = high_threshold
        self.update_canny_edges()

    def update_canny_edges(self):
        self.edges = cv2.Canny(self.gray, self.canny_low, self.canny_high)
        self.edge_pixels_coords = np.where(self.edges > 0)
        self.num_edges = len(self.edge_pixels_coords[0])
        self.budget = int(self.num_edges * self.budget_ratio)

    def _precompute_gradients(self):
        grad_x = cv2.Sobel(self.gray, cv2.CV_64F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(self.gray, cv2.CV_64F, 0, 1, ksize=3)
        self.gradient_magnitude = np.sqrt(grad_x**2 + grad_y**2)
        self.gradient_angle = np.arctan2(grad_y, grad_x)
        max_mag = np.max(self.gradient_magnitude)
        if max_mag > 0:
            self.gradient_magnitude /= max_mag

    # ... (辅助函数 _get_neighbors, _compute_edge_importance 基本不变)
    def _get_neighbors(self, y, x, radius=2):
        y_min, y_max = max(0, y - radius), min(self.height, y + radius + 1)
        x_min, x_max = max(0, x - radius), min(self.width, x + radius + 1)
        return [
            (ny, nx)
            for ny in range(y_min, y_max)
            for nx in range(x_min, x_max)
            if (ny, nx) != (y, x)
        ]

    def _compute_edge_importance(self, y, x, current_selection):
        if not self.edges[y, x]:
            return 0
        importance = self.gradient_magnitude[y, x]
        connectivity = 0
        neighbors = self._get_neighbors(y, x, radius=1)
        for ny, nx in neighbors:
            if current_selection[ny, nx]:
                connectivity += 1
        importance += 0.5 * (connectivity / 8.0)
        return importance

    def optimize_edges(self, main_body_mask=None, detail_mask=None):
        # 1. 确定搜索空间 (核心改动，实现背景抑制)
        search_space_mask = np.zeros_like(self.gray, dtype=bool)
        has_main_body_mask = main_body_mask is not None and np.any(main_body_mask)

        # 如果有主体蒙版，搜索空间就是该蒙版；否则是整张图
        if has_main_body_mask:
            search_space_mask = main_body_mask
        else:
            search_space_mask.fill(True)

        # 2. 确定强制保留的区域
        user_keep = np.zeros_like(self.gray, dtype=bool)
        if has_main_body_mask:
            user_keep |= main_body_mask
        if detail_mask is not None and np.any(detail_mask):
            user_keep |= detail_mask

        # 确保强制保留的点必须是Canny边缘上的点
        user_keep &= self.edges.astype(bool)

        # 3. 贪心算法
        current_selection = user_keep.copy()

        # 建立候选列表，只从搜索空间内选取
        candidates = []
        # 将Canny边缘与搜索空间取交集
        valid_edge_coords_y, valid_edge_coords_x = np.where(
            (self.edges > 0) & search_space_mask
        )

        for y, x in zip(valid_edge_coords_y, valid_edge_coords_x):
            if not current_selection[y, x]:
                importance = self.gradient_magnitude[y, x]
                candidates.append((importance, y, x))

        candidates.sort(key=lambda item: item[0], reverse=True)

        # 根据预算填充
        selected_count = np.sum(current_selection)
        budget = int(
            np.sum(search_space_mask & self.edges.astype(bool)) * self.budget_ratio
        )
        if not has_main_body_mask:
            budget = self.budget  # 如果没有蒙版，使用全局预算

        for _, y, x in candidates:
            if selected_count >= budget:
                break
            current_importance = self._compute_edge_importance(y, x, current_selection)
            if current_importance > 0:
                current_selection[y, x] = True
                selected_count += 1

        # 4. 后处理，实现粗实线和平滑效果
        sketch = current_selection.astype(np.uint8) * 255
        # 加粗线条
        kernel = np.ones((3, 3), np.uint8)
        sketch = cv2.dilate(sketch, kernel, iterations=1)
        # 平滑并去噪
        sketch = cv2.medianBlur(sketch, 3)

        return sketch


# 升级版 auto_canny
def auto_canny(image_gray, sigma=0.33, mask=None):
    """
    更智能的 Canny 阈值检测
    - 如果提供了蒙版，只在蒙版区域内计算
    - 使用 Otsu's 方法来确定上限阈值，更鲁棒
    """
    if mask is not None and np.any(mask):
        # 只在蒙版区域内计算
        masked_gray = cv2.bitwise_and(
            image_gray, image_gray, mask=mask.astype(np.uint8)
        )
        # 计算Otsu阈值，它会忽略黑色像素(0)
        high_threshold, _ = cv2.threshold(
            masked_gray[mask], 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
    else:
        # 在整张图上计算
        high_threshold, _ = cv2.threshold(
            image_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

    low_threshold = 0.5 * high_threshold

    return int(low_threshold), int(high_threshold)
