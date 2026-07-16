import { Form, Row, Col } from 'react-bootstrap';

function Output(props) {
	return (
		<div className="offset-md-1">
			<Form>
				<Form.Group as={Row} className="mb-3" controlId="entered-equation">
					<Form.Label column sm="3">
						Entered Equation
					</Form.Label>
					<Col sm="5">
						<Form.Control readOnly value={props.equation || ""} />
					</Col>
				</Form.Group>
				<Form.Group as={Row} className="mb-3" controlId="formatted-equation">
					<Form.Label column sm="3">
						Formatted Equation
					</Form.Label>
					<Col sm="5">
						<Form.Control readOnly value={props.formatted_equation || ""} />
					</Col>
				</Form.Group>
				<Form.Group as={Row} className="mb-3" controlId="result">
					<Form.Label column sm="3">
						Result
					</Form.Label>
					<Col sm="5">
						<Form.Control readOnly value={props.result || ""} />
					</Col>
				</Form.Group>
			</Form>
		</div>
	);
}

export default Output;
