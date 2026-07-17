import './App.css';
import Canvas from './Canvas';
import ErrorBoundary from './ErrorBoundary';

function App() {
  return (
    <div className="App">
      <ErrorBoundary>
        <Canvas />
      </ErrorBoundary>
    </div>
  );
}

export default App;
