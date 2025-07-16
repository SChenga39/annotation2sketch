import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';

const ImageCanvas = forwardRef(({ baseImage, brushColor, brushSize, imageSize }, ref) => {
  const canvasRef = useRef(null); // 主显示画布
  const maskCanvasRef = useRef(null);   // 不可见的蒙版画布 (用于累积填充区域)
  const [isDrawing, setIsDrawing] = useState(false);
  const [currentPath, setCurrentPath] = useState([]);

  // 初始化蒙版画布
  useEffect(() => {
    if (imageSize.width > 0) {
      const maskCanvas = maskCanvasRef.current;
      maskCanvas.width = imageSize.width;
      maskCanvas.height = imageSize.height;
      const ctx = maskCanvas.getContext('2d');
      ctx.clearRect(0, 0, maskCanvas.width, maskCanvas.height);
    }
  }, [imageSize]);

  useImperativeHandle(ref, () => ({
    getMaskAsBase64: () => {
      const maskCanvas = maskCanvasRef.current;
      // 检查蒙版是否为空
      const context = maskCanvas.getContext('2d');
      const imageData = context.getImageData(0, 0, maskCanvas.width, maskCanvas.height).data;
      const isEmpty = !imageData.some(channel => channel !== 0);

      if (isEmpty) return null;

      return maskCanvas.toDataURL('image/png').split(',')[1];
    },
    clearCanvas: () => {
      const maskCtx = maskCanvasRef.current.getContext('2d');
      maskCtx.clearRect(0, 0, maskCanvasRef.current.width, maskCanvasRef.current.height);
      setCurrentPath([]); // 同时清空当前正在画的路径
    },
  }));

  // 主绘制效果
  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (baseImage) {
      const img = new Image();
      img.src = baseImage;
      img.onload = () => {
        canvas.width = imageSize.width;
        canvas.height = imageSize.height;
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

        // 绘制已确认的蒙版区域
        ctx.globalAlpha = 0.5; // 半透明
        ctx.drawImage(maskCanvasRef.current, 0, 0);
        ctx.globalAlpha = 1.0;

        // 绘制当前正在画的路径
        drawPath(ctx, currentPath, brushColor, brushSize);
      };
    } else if (imageSize.width > 0) {
      // 如果没有图像，但有尺寸，则绘制一个占位符
      canvas.width = imageSize.width;
      canvas.height = imageSize.height;
      ctx.fillStyle = '#f0f0f0';
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = '#aaa';
      ctx.font = '20px Arial';
      ctx.textAlign = 'center';
      ctx.fillText('Upload an image to start', canvas.width / 2, canvas.height / 2);
    }
  }, [baseImage, imageSize, currentPath, brushColor, brushSize]); // 依赖项现在包括 currentPath

  const drawPath = (ctx, path, color, size) => {
    if (path.length < 2) return;
    ctx.strokeStyle = color;
    ctx.lineWidth = size;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.beginPath();
    ctx.moveTo(path[0].x, path[0].y);
    for (let i = 1; i < path.length; i++) {
      ctx.lineTo(path[i].x, path[i].y);
    }
    ctx.stroke();
  };

  const getCoords = (e) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return { x: (e.clientX - rect.left) * scaleX, y: (e.clientY - rect.top) * scaleY };
  };

  const startDrawing = (e) => {
    if (!baseImage) return;
    setIsDrawing(true);
    setCurrentPath([getCoords(e)]);
  };

  const draw = (e) => {
    if (!isDrawing) return;
    setCurrentPath(prev => [...prev, getCoords(e)]);
  };

  const stopDrawing = () => {
    if (!isDrawing || currentPath.length < 2) {
        setIsDrawing(false);
        return;
    }

    // "圈选填充" 逻辑
    const maskCtx = maskCanvasRef.current.getContext('2d');
    maskCtx.fillStyle = 'white'; // 填充白色区域到蒙版
    maskCtx.beginPath();
    maskCtx.moveTo(currentPath[0].x, currentPath[0].y);
    for (let i = 1; i < currentPath.length; i++) {
        maskCtx.lineTo(currentPath[i].x, currentPath[i].y);
    }
    maskCtx.closePath(); // 自动闭合起点和终点
    maskCtx.fill();

    setIsDrawing(false);
    setCurrentPath([]); // 清空当前路径，因为它已经被固化到蒙版层
  };

  return (
    <>
      <canvas
        ref={canvasRef}
        onMouseDown={startDrawing}
        onMouseMove={draw}
        onMouseUp={stopDrawing}
        onMouseLeave={stopDrawing}
        style={{ maxWidth: '100%', maxHeight: '100%', cursor: 'crosshair', objectFit: 'contain' }}
      />
      {/* 隐藏的蒙版画布 */}
      <canvas ref={maskCanvasRef} style={{ display: 'none' }} />
    </>
  );
});

export default ImageCanvas;
