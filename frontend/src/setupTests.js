import '@testing-library/jest-dom/vitest';

// jsdom has no 2D canvas; the drawing surface tolerates a null context
HTMLCanvasElement.prototype.getContext = () => null;
