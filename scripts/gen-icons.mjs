import { deflateSync } from "node:zlib";
import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const OUT = join(process.cwd(), "public", "icons");
mkdirSync(OUT, { recursive: true });

const crcTable = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

function crc32(buf) {
  let c = 0xffffffff;
  for (let i = 0; i < buf.length; i++) c = crcTable[(c ^ buf[i]) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const typeBuf = Buffer.from(type, "ascii");
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(Buffer.concat([typeBuf, data])));
  return Buffer.concat([len, typeBuf, data, crc]);
}

function encodePNG(width, height, rgba) {
  const sig = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(width, 0);
  ihdr.writeUInt32BE(height, 4);
  ihdr.writeUInt8(8, 8); // bit depth
  ihdr.writeUInt8(6, 9); // color type RGBA
  const raw = Buffer.alloc(height * (1 + width * 4));
  for (let y = 0; y < height; y++) {
    raw[y * (1 + width * 4)] = 0; // filter none
    rgba.copy(raw, y * (1 + width * 4) + 1, y * width * 4, (y + 1) * width * 4);
  }
  const idat = deflateSync(raw, { level: 9 });
  return Buffer.concat([sig, chunk("IHDR", ihdr), chunk("IDAT", idat), chunk("IEND", Buffer.alloc(0))]);
}

function hexC(hex) {
  return [
    parseInt(hex.slice(1, 3), 16),
    parseInt(hex.slice(3, 5), 16),
    parseInt(hex.slice(5, 7), 16),
  ];
}

function inRoundedRect(x, y, w, h, cx, cy, r) {
  if (x < cx || y < cy || x > cx + w || y > cy + h) return false;
  const dx = Math.max(cx + r - x, 0, x - (cx + w - r));
  const dy = Math.max(cy + r - y, 0, y - (cy + h - r));
  return dx * dx + dy * dy <= r * r;
}

function drawIcon(size, { maskable = false }) {
  const buf = Buffer.alloc(size * size * 4);
  const BLUE = hexC("#0075de");
  const WHITE = [255, 255, 255];
  const INK = hexC("#02093a");
  const MARIGOLD = hexC("#ffb110");

  // safe area for maskable icons
  const min = maskable ? 0.125 * size : 0;
  const max = size - min;

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const i = (y * size + x) * 4;
      const inside = maskable ? true : inRoundedRect(x, y, size, size, 0, 0, size * 0.22);

      let r = 0, g = 0, b = 0, a = 0;
      if (inside) {
        [r, g, b] = BLUE;
        a = 255;

        // document card
        const docW = (max - min) * 0.56;
        const docH = (max - min) * 0.72;
        const docX = size / 2 - docW / 2;
        const docY = size / 2 - docH / 2;
        const isDoc = inRoundedRect(x, y, docW, docH, docX, docY, docW * 0.16);

        if (isDoc) {
          [r, g, b] = WHITE;

          const lineH = docH * 0.09;
          // ketebalan wajah: bar stabilo kuning
          const isHl =
            y >= size * 0.5 &&
            y <= size * 0.5 + docH * 0.22 &&
            x >= docX + docW * 0.14 &&
            x <= docX + docW * 0.86;

          // garis teks
          const t1 = y >= size * 0.375 && y < size * 0.375 + lineH && x >= docX + docW * 0.18 && x <= docX + docW * 0.82;
          const t2 = y >= size * 0.66 && y < size * 0.66 + lineH && x >= docX + docW * 0.18 && x <= docX + docW * 0.68;
          const t3 = y >= size * 0.76 && y < size * 0.76 + lineH && x >= docX + docW * 0.18 && x <= docX + docW * 0.56;

          if (isHl) [r, g, b] = MARIGOLD;
          else if (t1 || t2 || t3) [r, g, b] = INK;
        }
      }
      buf[i] = r;
      buf[i + 1] = g;
      buf[i + 2] = b;
      buf[i + 3] = a;
    }
  }
  return encodePNG(size, size, buf);
}

for (const [name, size, opts] of [
  ["icon-192.png", 192, { maskable: false }],
  ["icon-512.png", 512, { maskable: false }],
  ["icon-maskable-512.png", 512, { maskable: true }],
  ["apple-touch-icon.png", 180, { maskable: false }],
]) {
  writeFileSync(join(OUT, name), drawIcon(size, opts));
  console.log("wrote", name);
}
