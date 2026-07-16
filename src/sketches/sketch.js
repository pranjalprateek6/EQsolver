export default function sketch(p) {
    let lastClearCount = 0;

    p.setup = () => {
        p.createCanvas(550, 300);
        // white background so the exported PNG is not transparent
        p.background(255);
    };

    p.draw = () => {};

    p.mouseDragged = () => {
        p.stroke(0);
        p.strokeWeight(3);
        p.line(p.mouseX, p.mouseY, p.pmouseX, p.pmouseY);
    };

    p.myCustomRedrawAccordingToNewPropsHandler = (props) => {
        if (props.clearCount !== undefined && props.clearCount !== lastClearCount) {
            lastClearCount = props.clearCount;
            p.background(255);
        }
    };
}
