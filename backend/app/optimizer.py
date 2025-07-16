import heapq

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
    def _get_neighbors(self, y, x, radius=1):  # Radius 1 is sufficient for this model
        neighbors = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dy == 0 and dx == 0:
                    continue
                ny, nx = y + dy, x + dx
                if 0 <= ny < self.height and 0 <= nx < self.width:
                    neighbors.append((ny, nx))
        return neighbors

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

    # This is the NEW optimization function based on the energy formulation
    def optimize_edges_energy(
        self, main_body_mask=None, detail_mask=None, lambda1=1.5, lambda2=2.0
    ):
        """
        Optimizes edge selection by greedily minimizing the energy function.
        Uses a priority queue for efficiency.
        """

        # 1. Determine Search Space & Budget
        search_space_mask = np.zeros_like(self.gray, dtype=bool)
        has_main_body_mask = main_body_mask is not None and np.any(main_body_mask)
        if has_main_body_mask:
            search_space_mask = main_body_mask
        else:
            search_space_mask.fill(True)

        # Canny edges within our search space
        valid_edges_mask = (self.edges > 0) & search_space_mask

        # Adjust budget based on the number of edges in the search space
        budget = int(np.sum(valid_edges_mask) * self.budget_ratio)

        # 2. Handle User Constraints (Forced Selections)
        current_selection = np.zeros_like(self.gray, dtype=bool)
        if has_main_body_mask:
            current_selection |= main_body_mask
        if detail_mask is not None and np.any(detail_mask):
            current_selection |= detail_mask

        # Force selected pixels to be on a valid Canny edge
        current_selection &= valid_edges_mask

        # 3. Initialize Priority Queue for Greedy Algorithm
        # heapq is a min-heap, so we store negative gain
        # Item format: (-gain, y, x)
        pq = []

        # Map to store the current gain of each pixel to avoid recomputing
        # Key: (y, x), Value: gain
        pixel_gains = {}

        # Add all valid candidate pixels to the priority queue
        candidate_coords_y, candidate_coords_x = np.where(
            valid_edges_mask & ~current_selection
        )
        for y, x in zip(candidate_coords_y, candidate_coords_x):
            # Initial gain is just saliency, as there are no selected neighbors yet
            saliency = self.gradient_magnitude[y, x]
            pixel_gains[(y, x)] = saliency
            heapq.heappush(pq, (-saliency, y, x))

        # 4. Greedy Selection Loop
        selected_count = np.sum(current_selection)
        while pq and selected_count < budget:
            # Get pixel with the highest marginal gain
            neg_gain, y, x = heapq.heappop(pq)
            gain = -neg_gain

            # Stale entry check: if the popped gain is not the current gain, skip it
            if gain < pixel_gains.get((y, x), -1):
                continue

            # If already selected (by a user mask after initialization), skip
            if current_selection[y, x]:
                continue

            # Add pixel to solution
            current_selection[y, x] = True
            selected_count += 1

            # Update gains of its neighbors
            for ny, nx in self._get_neighbors(y, x):
                if valid_edges_mask[ny, nx] and not current_selection[ny, nx]:
                    # Current gain of the neighbor
                    neighbor_gain = pixel_gains.get(
                        (ny, nx), self.gradient_magnitude[ny, nx]
                    )

                    # Add connectivity reward (+lambda1)
                    neighbor_gain += lambda1

                    # Add parallel penalty (-lambda2 * cos^2)
                    angle_p = self.gradient_angle[y, x]
                    angle_q = self.gradient_angle[ny, nx]
                    cos_theta_sq = np.cos(angle_p - angle_q) ** 2
                    neighbor_gain -= lambda2 * cos_theta_sq

                    # Update the gain and push to the priority queue
                    pixel_gains[(ny, nx)] = neighbor_gain
                    heapq.heappush(pq, (-neighbor_gain, ny, nx))

        # 5. Post-processing for final style
        sketch = current_selection.astype(np.uint8) * 255
        kernel = np.ones((3, 3), np.uint8)
        sketch = cv2.dilate(sketch, kernel, iterations=1)
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
