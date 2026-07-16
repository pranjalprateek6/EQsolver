import { useState } from 'react';
import { Button, Modal, Image, Alert } from 'react-bootstrap';

const VALID_EXTENSIONS = ['jpg', 'jpeg', 'png'];

function UploadButton({ sendImgToServer, disabled }) {
    const [imgBase64, setImgBase64] = useState('');
    const [imgUrl, setImgUrl] = useState('');
    const [uploadError, setUploadError] = useState(false);
    const [showModal, setShowModal] = useState(false);

    const validateFile = (event) => {
        const file = event.target.files[0];
        if (!file) return;
        const extension = file.name.substring(file.name.lastIndexOf('.') + 1).toLowerCase();
        if (VALID_EXTENSIONS.includes(extension)) {
            const reader = new FileReader();
            reader.onloadend = () => {
                setImgBase64(reader.result);
                setImgUrl(URL.createObjectURL(file));
                setUploadError(false);
                setShowModal(true);
            };
            reader.readAsDataURL(file);
        } else {
            setImgBase64('');
            setImgUrl('');
            setUploadError(true);
            setShowModal(true);
        }
    };

    return (
        <div>
            <div>
                <input type="file" accept=".jpg,.jpeg,.png" onChange={validateFile} />
                <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!imgBase64 || disabled}
                    onClick={() => sendImgToServer(imgBase64)}>
                    Upload!
                </button>
            </div>
            <Modal
                show={showModal}
                onHide={() => setShowModal(false)}
                size="lg"
                aria-labelledby="contained-modal-title-vcenter"
            >
                <Modal.Header closeButton>
                    <Modal.Title>
                        {uploadError ? "Error in extension" : "Preview of selected image"}
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body>
                    {uploadError ? (
                        <Alert variant="danger">
                            The selected file is not an image. Please select an image
                        </Alert>
                    ) : (
                        <Image alt="selected image" src={imgUrl} fluid />
                    )}
                </Modal.Body>
                <Modal.Footer>
                    <Button variant="secondary" onClick={() => setShowModal(false)}>
                        Close
                    </Button>
                </Modal.Footer>
            </Modal>
        </div>
    );
}

export default UploadButton;
