import { scrubEvent, stripImages } from "./monitoring";

describe("monitoring", () => {
  it("drops request bodies, cookies and the user", () => {
    const event = scrubEvent({
      request: { url: "/predict", data: '{"image":"abc"}', cookies: "c" },
      user: { ip_address: "1.2.3.4" },
      message: "boom",
    });
    expect(event).toEqual({ request: { url: "/predict" }, message: "boom" });
  });

  it("blanks image fields and image-like strings anywhere", () => {
    expect(
      stripImages({
        image: "short",
        nested: [{ tile: "data:image/png;base64,iVBOR" }, "A".repeat(3000)],
        expression: "x+1=2",
      })
    ).toEqual({
      image: "[removed]",
      nested: [{ tile: "[removed]" }, "[removed]"],
      expression: "x+1=2",
    });
  });
});
