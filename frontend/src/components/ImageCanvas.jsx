import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';

const ImageCanvas = forwardRef(({ baseImage, brushColor, brushSize, imageSize }, ref) => {
  const canvasRef = useRef(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [paths, setPaths] = useState([]);

  useImperativeHandle(ref, () => ({
    getMaskAsBase64: () => {
      if (paths.length === 0) return null;
      const canvas = canvasRef.current;
      const maskCanvas = document.createElement('canvas');
      maskCanvas.width = canvas.width;
      maskCanvas.height = canvas.height;
      const maskCtx = maskCanvas.getContext('2d');

      maskCtx.fillStyle = 'black';
      maskCtx.fillRect(0, 0, maskCanvas.width, maskCanvas.height);

      drawPaths(maskCtx, paths, brushSize, 'white');

      return maskCanvas.toDataURL('image/png').split(',')[1];
    },
    clearCanvas: () => {
      setPaths([]);
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
        // 使用从后端获取的精确尺寸
        canvas.width = imageSize.width;
        canvas.height = imageSize.height;
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        drawPaths(ctx, paths, brushSize, brushColor);
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
  }, [baseImage, paths, brushColor, brushSize, imageSize]);

  const drawPaths = (ctx, pathList, size, color) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = size;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    pathList.forEach(path => {
      if (path.length < 2) return;
      ctx.beginPath();
      ctx.moveTo(path[0].x, path[0].y);
      for (let i = 1; i < path.length; i++) {
        ctx.lineTo(path[i].x, path[i].y);
      }
      ctx.stroke();
    });
  };

  const getCoords = (event) => {
    const canvas = canvasRef.current;
    const rect = canvas.getBoundingClientRect();
    const scaleX = canvas.width / rect.width;
    const scaleY = canvas.height / rect.height;
    return { x: (event.clientX - rect.left) * scaleX, y: (event.clientY - rect.top) * scaleY };
  };

  const startDrawing = (e) => {
    if (!baseImage) return;
    const { x, y } = getCoords(e);
    setPaths(prev => [...prev, [{ x, y }]]);
    setIsDrawing(true);
  };

  const draw = (e) => {
    if (!isDrawing) return;
    const { x, y } = getCoords(e);
    setPaths(prev => {
      const newPaths = [...prev];
      newPaths[newPaths.length - 1].push({ x, y });
      return newPaths;
    });
  };

  const stopDrawing = () => setIsDrawing(false);

  return (
    <canvas
      ref={canvasRef}
      onMouseDown={startDrawing}
      onMouseMove={draw}
      onMouseUp={stopDrawing}
      onMouseLeave={stopDrawing}
      style={{ maxWidth: '100%', maxHeight: '100%', cursor: 'crosshair', objectFit: 'contain' }}
    />
  );
});

export default ImageCanvas;
