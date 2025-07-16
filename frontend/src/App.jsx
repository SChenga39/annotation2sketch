import { useRef, useState } from 'react';
import './App.css';
import Controls from './components/Controls';
import ImageCanvas from './components/ImageCanvas';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  // --- STATE MANAGEMENT ---
  const [session, setSession] = useState({ id: null, originalImage: null, imageSize: { width: 0, height: 0 } });
  const [cannyImage, setCannyImage] = useState(null);
  const [previewSketch, setPreviewSketch] = useState(null); // 上方草图
  const [finalSketch, setFinalSketch] = useState(null);     // 下方草图
  const [controlParams, setControlParams] = useState(null);
  const [brushSize, setBrushSize] = useState(15); // Brush size state 统一在这里管理
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  // --- REFS FOR CANVASES ---
  const mainBodyCanvasApi = useRef();
  const detailCanvasApi = useRef();

  // --- API & EVENT HANDLERS ---
  const handleImageUpload = async (file) => {
    setIsLoading(true);
    setError('');
    // Clear all previous results
    setPreviewSketch(null);
    setFinalSketch(null);
    setCannyImage(null);
    mainBodyCanvasApi.current?.clearCanvas();
    detailCanvasApi.current?.clearCanvas();

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_BASE_URL}/upload`, { method: 'POST', body: formData });
      if (!response.ok) throw new Error('Image upload failed.');
      const data = await response.json();

      setSession({
        id: data.session_id,
        originalImage: `data:image/jpeg;base64,${data.original_image_b64}`,
        imageSize: { width: data.image_width, height: data.image_height }
      });
      setCannyImage(`data:image/png;base64,${data.initial_edges_b64}`);
      setControlParams({ cannyLow: data.canny_low, cannyHigh: data.canny_high });

    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  // Reusable function to call the process endpoint
  const generateSketch = async (options) => {
    if (!session.id) return null;
    setIsLoading(true);
    setError('');
    try {
      const response = await fetch(`${API_BASE_URL}/process`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: session.id,
          main_body_mask_b64: options.mainBodyMask,
          detail_mask_b64: options.detailMask,
          budget_ratio: options.budget,
        }),
      });
      if (!response.ok) throw new Error('Failed to generate sketch.');
      const data = await response.json();
      return `data:image/png;base64,${data.sketch_b64}`;
    } catch (err) {
      setError(err.message);
      return null;
    } finally {
      setIsLoading(false);
    }
  };

  // Handler for the "Generate Preview" button
  const handleGeneratePreview = async ({ budget }) => {
    const mainBodyMask = mainBodyCanvasApi.current.getMaskAsBase64();
    const result = await generateSketch({ mainBodyMask, budget });
    if (result) {
      setPreviewSketch(result);
    }
  };

  // Handler for the "Generate Final Sketch" button
  const handleGenerateFinal = async ({ budget }) => {
    const mainBodyMask = mainBodyCanvasApi.current.getMaskAsBase64();
    const detailMask = detailCanvasApi.current.getMaskAsBase64();
    const result = await generateSketch({ mainBodyMask, detailMask, budget });
    if (result) {
      setFinalSketch(result);
    }
  };

  const handleCannyChange = async ({ cannyLow, cannyHigh }) => {
    // ... (This function remains unchanged)
    if (!session.id) return;
    try {
      const response = await fetch(`${API_BASE_URL}/update-canny`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: session.id, canny_low: cannyLow, canny_high: cannyHigh }),
      });
      if (!response.ok) throw new Error('Failed to update Canny edges.');
      const data = await response.json();
      setCannyImage(`data:image/png;base64,${data.edges_b64}`);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleAutoTuneCanny = async () => {
    if (!session.id) return;
    setIsLoading(true);
    // 获取主体高亮蒙版
    const mainBodyMask = mainBodyCanvasApi.current.getMaskAsBase64();
    try {
        const response = await fetch(`${API_BASE_URL}/autotune-canny`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: session.id,
                main_body_mask_b64: mainBodyMask // 发送蒙版
            })
        });
        if (!response.ok) throw new Error('Auto-tuning failed.');
        const data = await response.json();
        // 更新滑块和 Canny 结果
        setControlParams({ cannyLow: data.canny_low, cannyHigh: data.canny_high });
        await handleCannyChange({ cannyLow: data.canny_low, cannyHigh: data.canny_high });
    } catch (err) {
        setError(err.message);
    } finally {
        setIsLoading(false);
    }
  };

  const handleClear = () => {
    mainBodyCanvasApi.current.clearCanvas();
    detailCanvasApi.current.clearCanvas();
    setPreviewSketch(null);
    setFinalSketch(null);
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Interactive Sketch Generation Workflow</h1>
      </header>
      <main className="App-main">
        <div className="controls-container">
          <Controls
            session={session.id}
            onImageUpload={handleImageUpload}
            onGeneratePreview={handleGeneratePreview}
            onGenerateFinal={handleGenerateFinal}
            onClear={handleClear}
            onCannyChange={handleCannyChange}
            onAutoTune={handleAutoTuneCanny}
            disabled={isLoading}
            initialParams={controlParams}
            brushSize={brushSize}
            onBrushSizeChange={setBrushSize}
          />
           {error && <p className="error-message">{error}</p>}
        </div>

        {isLoading && <div className="loading-overlay"><div className="loader"></div></div>}

        <div className="main-grid">
          {/* --- Top Row --- */}
          <div className="grid-item" style={{'gridArea': 'highlight'}}>
            <h3>1. Highlight Subject</h3>
            <ImageCanvas
              ref={mainBodyCanvasApi}
              baseImage={session.originalImage}
              brushColor="rgba(0, 255, 0, 0.7)"
              brushSize={brushSize}
              imageSize={session.imageSize}
            />
          </div>
          <div className="grid-item" style={{'gridArea': 'canny'}}>
            <h3>Canny Edges</h3>
            {cannyImage ? <img src={cannyImage} alt="Canny Edges" /> : <div className="placeholder">Canny Edges</div>}
          </div>
          <div className="grid-item" style={{'gridArea': 'preview'}}>
            <h3>2. Preview Sketch</h3>
            {previewSketch ? <img src={previewSketch} alt="Preview Sketch" /> : <div className="placeholder">Preview Result</div>}
          </div>

          {/* --- Bottom Row --- */}
          <div className="grid-item" style={{'gridArea': 'details'}}>
            <h3>3. Add Details</h3>
            <ImageCanvas
              ref={detailCanvasApi}
              baseImage={session.originalImage}
              brushColor="rgba(255, 165, 0, 0.7)"
              brushSize={brushSize}
              imageSize={session.imageSize}
            />
          </div>
          <div className="grid-item" style={{'gridArea': 'final'}}>
            <h3>4. Final Sketch</h3>
            {finalSketch ? <img src={finalSketch} alt="Final Sketch" /> : <div className="placeholder">Final Result</div>}
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
