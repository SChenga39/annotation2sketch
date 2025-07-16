import React, { useEffect, useRef } from 'react';

// 注意 props 新增了 brushSize 和 onBrushSizeChange
function Controls({
  session,
  onImageUpload,
  onGeneratePreview,
  onGenerateFinal,
  onClear,
  onCannyChange,
  onAutoTune,
  disabled,
  initialParams,
  brushSize,
  onBrushSizeChange
}) {
  const [budget, setBudget] = React.useState(0.3);
  const [cannyLow, setCannyLow] = React.useState(initialParams?.cannyLow || 50);
  const [cannyHigh, setCannyHigh] = React.useState(initialParams?.cannyHigh || 150);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (initialParams) {
      setCannyLow(initialParams.cannyLow);
      setCannyHigh(initialParams.cannyHigh);
    }
  }, [initialParams]);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      onImageUpload(e.target.files[0]);
    }
  };

  const handleCannySliderChange = () => {
    const low = Math.min(cannyLow, cannyHigh - 1);
    const high = Math.max(cannyHigh, cannyLow + 1);
    onCannyChange({ cannyLow: low, cannyHigh: high });
  };

  // 将参数打包传递
  const handlePreview = () => onGeneratePreview({ budget, brushSize });
  const handleFinal = () => onGenerateFinal({ budget, brushSize });

  return (
    <div className="controls">
      <div className="control-group">
        <h4>File & Actions</h4>
        <input type="file" accept="image/*" onChange={handleFileChange} ref={fileInputRef} style={{ display: 'none' }}/>
        <button onClick={() => fileInputRef.current.click()} disabled={disabled}>Upload Image</button>
        {/* 分成两个生成按钮 */}
        <button onClick={handlePreview} disabled={!session || disabled} className="generate-button-preview">
          Generate Preview
        </button>
        <button onClick={handleFinal} disabled={!session || disabled} className="generate-button-final">
          Generate Final Sketch
        </button>
        <button onClick={onClear} disabled={!session || disabled}>Clear All</button>
      </div>

      <div className="control-group">
        <h4>Brush & Detail</h4>
        <label>Brush Size: {brushSize}</label>
        <input type="range" min="2" max="50" value={brushSize} onChange={(e) => onBrushSizeChange(parseInt(e.target.value))} disabled={!session}/>
        <label>Detail Level (Budget): {budget.toFixed(2)}</label>
        <input type="range" min="0.1" max="1.0" step="0.05" value={budget} onChange={(e) => setBudget(parseFloat(e.target.value))} disabled={!session}/>
      </div>

      <div className="control-group">
        <h4>Canny Edge Detector</h4>
        <button onClick={onAutoTune} disabled={!session || disabled}>Auto-Tune</button>
        <label>Low: {cannyLow}</label>
        <input type="range" min="1" max="254" value={cannyLow} onChange={(e) => setCannyLow(parseInt(e.target.value))} onMouseUp={handleCannySliderChange} disabled={!session}/>
        <label>High: {cannyHigh}</label>
        <input type="range" min="1" max="254" value={cannyHigh} onChange={(e) => setCannyHigh(parseInt(e.target.value))} onMouseUp={handleCannySliderChange} disabled={!session}/>
      </div>
    </div>
  );
}

export default Controls;
