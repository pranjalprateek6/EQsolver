import { useRef, useState } from 'react';
import { Button, Modal, Image, Alert } from 'react-bootstrap';

const VALID_TYPES = ['image/png', 'image/jpeg', 'image/webp'];
// the server refuses request bodies over 10 MB, and base64 adds a third
const MAX_FILE_BYTES = 7 * 1024 * 1024;

// Read an image File into a data URL, or reject with a message for the user.
export function readImageFile(file) {
    return new Promise((resolve, reject) => {
        if (!file) {
            reject(new Error('No file was selected.'));
            return;
        }
        if (!VALID_TYPES.includes(file.type)) {
            reject(new Error('That file is not a PNG, JPEG or WebP image.'));
            return;
        }
        if (file.size > MAX_FILE_BYTES) {
            reject(new Error('That image is over 7 MB. Try a smaller photo or crop it to the equation.'));
            return;
        }
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error('Could not read that file.'));
        reader.readAsDataURL(file);
    });
}

// Pick an image, preview it, and send it with one click from the preview.
// Drag-drop and paste onto the canvas use readImageFile directly.
function UploadButton({ sendImgToServer, disabled }) {
    const [image, setImage] = useState('');
    const [fileName, setFileName] = useState('');
    const [uploadError, setUploadError] = useState('');
    const [showModal, setShowModal] = useState(false);
    const inputRef = useRef(null);

    const onPick = async (event) => {
        const file = event.target.files[0];
        // let the same file be picked again after closing the preview
        event.target.value = '';
        if (!file) return;
        setFileName(file.name);
        try {
            setImage(await readImageFile(file));
            setUploadError('');
        } catch (err) {
            setImage('');
            setUploadError(err.message);
        }
        setShowModal(true);
    };

    const onRead = () => {
        setShowModal(false);
        sendImgToServer(image);
    };

    return (
        <div>
            <div className="upload">
                <label className="btn btn-outline-secondary upload__pick">
                    Upload a photo
                    <input
                        ref={inputRef}
                        type="file"
                        accept="image/png,image/jpeg,image/webp"
                        onChange={onPick}
                        hidden
                    />
                </label>
                <span className="upload__name">
                    {fileName || 'or drop or paste an image onto the canvas'}
                </span>
            </div>
            <Modal
                show={showModal}
                onHide={() => setShowModal(false)}
                size="lg"
                aria-labelledby="upload-preview-title"
                centered
            >
                <Modal.Header closeButton>
                    <Modal.Title id="upload-preview-title">
                        {uploadError ? "Can't use that file" : 'Read this image?'}
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    {uploadError ? (
                        <Alert variant="danger" className="mb-0">{uploadError}</Alert>
                    ) : (
                        image && <Image alt={`Preview of ${fileName}`} src={image} fluid />
                    )}
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="outline-secondary" onClick={() => setShowModal(false)}>
                        Cancel
                    </Button>
                    {uploadError ? (
                        <Button variant="primary" onClick={() => inputRef.current?.click()}>
                            Choose another
                        </Button>
                    ) : (
                        <Button variant="primary" onClick={onRead} disabled={disabled || !image}>
                            Read equation
                        </Button>
                    )}
                </Modal.Footer>
            </Modal>
        </div>
    );
}

export default UploadButton;
