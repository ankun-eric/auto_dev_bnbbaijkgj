/**
 * QR Code canvas component for WeChat Mini Program.
 * Uses canvas 2d API to render scannable QR codes.
 * Implements QR encoding internally (mode 4 byte, ECC level L).
 */

// --- QR Code encoding tables ---

const EC_CODEWORDS_PER_BLOCK = [
  // L, M, Q, H for versions 1..40
  [7,10,13,17],[10,16,22,28],[15,26,18,22],[20,18,26,16],[26,24,18,22],
  [18,16,24,28],[20,18,18,26],[24,22,22,26],[30,22,20,24],[18,26,24,28],
  [20,30,28,24],[24,22,26,28],[26,22,24,22],[30,24,20,24],[22,24,30,24],
  [24,28,24,30],[28,28,28,28],[30,26,28,28],[28,26,26,26],[28,26,28,28],
  [28,26,30,28],[28,28,24,30],[30,28,30,30],[30,28,30,30],[26,28,30,30],
  [28,28,28,30],[30,28,30,30],[30,28,30,30],[30,28,30,30],[30,28,30,30],
  [30,28,30,30],[30,28,30,30],[30,28,30,30],[30,28,30,30],[30,28,30,30],
  [30,28,30,30],[30,28,30,30],[30,28,30,30],[30,28,30,30],[30,28,30,30]
];

const NUM_EC_BLOCKS = [
  [1,1,1,1],[1,1,1,1],[1,1,2,2],[1,2,2,4],[1,2,4,4],
  [2,4,4,4],[2,4,6,5],[2,4,6,6],[2,5,8,8],[4,5,8,8],
  [4,5,8,11],[4,8,10,11],[4,9,12,16],[4,9,16,16],[6,10,12,18],
  [6,10,17,16],[6,11,16,19],[6,13,18,21],[7,14,21,25],[8,16,20,25],
  [8,17,23,25],[9,17,23,34],[9,18,25,30],[10,20,27,32],[12,21,29,35],
  [12,23,34,37],[12,25,34,40],[13,26,35,42],[14,28,38,45],[15,29,40,48],
  [16,31,43,51],[17,33,45,54],[18,35,48,57],[19,37,51,60],[19,38,53,63],
  [20,40,56,66],[21,43,59,70],[22,45,62,74],[24,47,65,77],[25,49,68,81]
];

const ALIGNMENT_PATTERN_POSITIONS = [
  [], [6,18], [6,22], [6,26], [6,30], [6,34],
  [6,22,38], [6,24,42], [6,26,46], [6,28,50], [6,30,54],
  [6,32,58], [6,34,62], [6,26,46,66], [6,26,48,70], [6,26,50,74],
  [6,30,54,78], [6,30,56,82], [6,30,58,86], [6,34,62,90],
  [6,28,50,72,94], [6,26,50,74,98], [6,30,54,78,102], [6,28,54,80,106],
  [6,32,58,84,110], [6,30,58,86,114], [6,34,62,90,118],
  [6,26,50,74,98,122], [6,30,54,78,102,126], [6,26,52,78,104,130],
  [6,30,56,82,108,134], [6,34,60,86,112,138], [6,30,58,86,114,142],
  [6,34,62,90,118,146], [6,30,54,78,102,126,150], [6,24,50,76,102,128,154],
  [6,28,54,80,106,132,158], [6,32,58,84,110,136,162],
  [6,26,54,82,110,138,166], [6,30,58,86,114,142,170]
];

const DATA_CAPACITY_BYTES = [
  [19,16,13,9],[34,28,22,16],[55,44,34,26],[80,64,48,36],[108,86,62,46],
  [136,108,76,60],[156,124,88,66],[194,154,110,86],[232,182,132,100],[274,216,154,122],
  [324,254,180,140],[370,290,206,158],[428,334,244,180],[461,365,261,197],[523,415,295,223],
  [589,453,325,253],[647,507,367,283],[721,563,397,313],[795,627,445,341],[861,669,485,385],
  [932,714,512,406],[1006,782,568,442],[1094,860,614,464],[1174,914,664,514],[1276,1000,718,538],
  [1370,1062,754,596],[1468,1128,808,628],[1531,1193,871,661],[1631,1267,911,701],[1735,1373,985,745],
  [1843,1455,1033,793],[1955,1541,1115,845],[2071,1631,1171,901],[2191,1725,1231,961],[2306,1812,1286,986],
  [2434,1914,1354,1054],[2566,1992,1426,1096],[2702,2102,1502,1142],[2812,2216,1582,1222],[2956,2334,1666,1276]
];

const FORMAT_INFO_STRINGS = [
  0x77c4, 0x72f3, 0x7daa, 0x789d, 0x662f, 0x6318, 0x6c41, 0x6976,
  0x5412, 0x5125, 0x5e7c, 0x5b4b, 0x45f9, 0x40ce, 0x4f97, 0x4aa0,
  0x355f, 0x3068, 0x3f31, 0x3a06, 0x24b4, 0x2183, 0x2eda, 0x2bed,
  0x1689, 0x13be, 0x1ce7, 0x19d0, 0x0762, 0x0255, 0x0d0c, 0x083b
];

const VERSION_INFO_STRINGS = [
  0, 0, 0, 0, 0, 0, 0x07c94, 0x085bc, 0x09a99, 0x0a4d3, 0x0bbf6, 0x0c762,
  0x0d847, 0x0e60d, 0x0f928, 0x10b78, 0x1145d, 0x12a17, 0x13532, 0x149a6,
  0x15683, 0x168c9, 0x177ec, 0x18ec4, 0x191e1, 0x1afab, 0x1b08e, 0x1cc1a,
  0x1d33f, 0x1ed75, 0x1f250, 0x209d5, 0x216f0, 0x228ba, 0x2379f, 0x24b0b,
  0x2542e, 0x26a64, 0x27541, 0x28c69
];

function getVersion(dataLen, ecl) {
  for (let v = 1; v <= 40; v++) {
    if (dataLen <= DATA_CAPACITY_BYTES[v - 1][ecl]) return v;
  }
  return -1;
}

function getCharCountBits(ver) {
  if (ver <= 9) return 8;
  return 16;
}

function encodeDataBytes(text) {
  const bytes = [];
  for (let i = 0; i < text.length; i++) {
    const c = text.charCodeAt(i);
    if (c < 0x80) {
      bytes.push(c);
    } else if (c < 0x800) {
      bytes.push(0xc0 | (c >> 6), 0x80 | (c & 0x3f));
    } else if (c >= 0xd800 && c <= 0xdbff && i + 1 < text.length) {
      const c2 = text.charCodeAt(i + 1);
      if (c2 >= 0xdc00 && c2 <= 0xdfff) {
        const cp = ((c - 0xd800) << 10) + (c2 - 0xdc00) + 0x10000;
        bytes.push(0xf0 | (cp >> 18), 0x80 | ((cp >> 12) & 0x3f), 0x80 | ((cp >> 6) & 0x3f), 0x80 | (cp & 0x3f));
        i++;
      }
    } else {
      bytes.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 0x3f), 0x80 | (c & 0x3f));
    }
  }
  return bytes;
}

function encodeData(text, ecl) {
  const rawBytes = encodeDataBytes(text);
  const version = getVersion(rawBytes.length, ecl);
  if (version < 0) throw new Error('Data too long for QR code');
  const totalCap = DATA_CAPACITY_BYTES[version - 1][ecl];
  const ccBits = getCharCountBits(version);

  const bits = [];
  function pushBits(val, len) {
    for (let i = len - 1; i >= 0; i--) bits.push((val >> i) & 1);
  }
  pushBits(4, 4); // byte mode
  pushBits(rawBytes.length, ccBits);
  for (const b of rawBytes) pushBits(b, 8);
  pushBits(0, Math.min(4, totalCap * 8 - bits.length));
  while (bits.length % 8 !== 0) bits.push(0);
  const pads = [0xec, 0x11];
  let pi = 0;
  while (bits.length < totalCap * 8) {
    pushBits(pads[pi], 8);
    pi ^= 1;
  }

  const dataBytes = [];
  for (let i = 0; i < bits.length; i += 8) {
    let b = 0;
    for (let j = 0; j < 8; j++) b = (b << 1) | bits[i + j];
    dataBytes.push(b);
  }

  return { version, dataBytes };
}

// GF(256) arithmetic
const GF_EXP = new Uint8Array(512);
const GF_LOG = new Uint8Array(256);
(function initGF() {
  let x = 1;
  for (let i = 0; i < 255; i++) {
    GF_EXP[i] = x;
    GF_LOG[x] = i;
    x = (x << 1) ^ (x >= 128 ? 0x11d : 0);
  }
  for (let i = 255; i < 512; i++) GF_EXP[i] = GF_EXP[i - 255];
})();

function gfMul(a, b) {
  if (a === 0 || b === 0) return 0;
  return GF_EXP[GF_LOG[a] + GF_LOG[b]];
}

function rsGenPoly(n) {
  let poly = [1];
  for (let i = 0; i < n; i++) {
    const newPoly = new Array(poly.length + 1).fill(0);
    const root = GF_EXP[i];
    for (let j = 0; j < poly.length; j++) {
      newPoly[j] ^= poly[j];
      newPoly[j + 1] ^= gfMul(poly[j], root);
    }
    poly = newPoly;
  }
  return poly;
}

function rsEncode(data, ecLen) {
  const gen = rsGenPoly(ecLen);
  const msg = new Uint8Array(data.length + ecLen);
  msg.set(data);
  for (let i = 0; i < data.length; i++) {
    const coef = msg[i];
    if (coef === 0) continue;
    for (let j = 0; j < gen.length; j++) {
      msg[i + j] ^= gfMul(gen[j], coef);
    }
  }
  return Array.from(msg.slice(data.length));
}

function interleaveBlocks(version, ecl, dataBytes) {
  const ecPerBlock = EC_CODEWORDS_PER_BLOCK[version - 1][ecl];
  const totalBlocks = NUM_EC_BLOCKS[version - 1][ecl];
  const totalDataBytes = DATA_CAPACITY_BYTES[version - 1][ecl];
  const shortBlockData = Math.floor(totalDataBytes / totalBlocks);
  const longBlocks = totalDataBytes % totalBlocks;
  const shortBlocks = totalBlocks - longBlocks;

  const dataBlocks = [];
  const ecBlocks = [];
  let offset = 0;
  for (let i = 0; i < totalBlocks; i++) {
    const len = shortBlockData + (i >= shortBlocks ? 1 : 0);
    const block = dataBytes.slice(offset, offset + len);
    offset += len;
    dataBlocks.push(block);
    ecBlocks.push(rsEncode(block, ecPerBlock));
  }

  const result = [];
  const maxDataLen = shortBlockData + 1;
  for (let i = 0; i < maxDataLen; i++) {
    for (let j = 0; j < totalBlocks; j++) {
      if (i < dataBlocks[j].length) result.push(dataBlocks[j][i]);
    }
  }
  for (let i = 0; i < ecPerBlock; i++) {
    for (let j = 0; j < totalBlocks; j++) {
      result.push(ecBlocks[j][i]);
    }
  }
  return result;
}

function createMatrix(version) {
  const size = version * 4 + 17;
  const matrix = Array.from({ length: size }, () => new Int8Array(size));
  const reserved = Array.from({ length: size }, () => new Uint8Array(size));

  function setPixel(r, c, val) {
    matrix[r][c] = val ? 1 : 0;
    reserved[r][c] = 1;
  }

  // Finder patterns
  for (const [row, col] of [[0, 0], [0, size - 7], [size - 7, 0]]) {
    for (let r = 0; r < 7; r++) {
      for (let c = 0; c < 7; c++) {
        const isBorder = r === 0 || r === 6 || c === 0 || c === 6;
        const isInner = r >= 2 && r <= 4 && c >= 2 && c <= 4;
        setPixel(row + r, col + c, isBorder || isInner ? 1 : 0);
      }
    }
  }

  // Separators
  for (let i = 0; i < 8; i++) {
    // top-left
    if (i < size) { setPixel(7, i, 0); setPixel(i, 7, 0); }
    // top-right
    if (size - 8 + i < size) { setPixel(7, size - 8 + i, 0); }
    if (i < 8) { setPixel(i, size - 8, 0); }
    // bottom-left
    if (size - 8 + i < size) { setPixel(size - 8, i, 0); }
    if (i < 8) { setPixel(size - 8 + i, 7, 0); }
  }

  // Timing patterns
  for (let i = 8; i < size - 8; i++) {
    setPixel(6, i, i % 2 === 0 ? 1 : 0);
    setPixel(i, 6, i % 2 === 0 ? 1 : 0);
  }

  // Dark module
  setPixel(size - 8, 8, 1);

  // Alignment patterns
  if (version >= 2) {
    const positions = ALIGNMENT_PATTERN_POSITIONS[version - 1];
    for (const r of positions) {
      for (const c of positions) {
        if (reserved[r][c]) continue;
        for (let dr = -2; dr <= 2; dr++) {
          for (let dc = -2; dc <= 2; dc++) {
            const isEdge = Math.abs(dr) === 2 || Math.abs(dc) === 2;
            const isCenter = dr === 0 && dc === 0;
            setPixel(r + dr, c + dc, isEdge || isCenter ? 1 : 0);
          }
        }
      }
    }
  }

  // Reserve format info areas
  for (let i = 0; i < 15; i++) {
    let r, c;
    if (i < 6) { r = i; c = 8; }
    else if (i < 8) { r = i + 1; c = 8; }
    else { r = size - 15 + i; c = 8; }
    if (!reserved[r][c]) { reserved[r][c] = 1; }

    if (i < 8) { r = 8; c = size - 1 - i; }
    else if (i < 9) { r = 8; c = 15 - i; }
    else { r = 8; c = 14 - i; }
    if (!reserved[r][c]) { reserved[r][c] = 1; }
  }

  // Reserve version info
  if (version >= 7) {
    for (let i = 0; i < 18; i++) {
      const r = Math.floor(i / 3);
      const c = size - 11 + (i % 3);
      reserved[r][c] = 1;
      reserved[c][r] = 1;
    }
  }

  return { matrix, reserved, size };
}

function placeData(matrix, reserved, size, bits) {
  let bitIdx = 0;
  let upward = true;
  for (let right = size - 1; right >= 1; right -= 2) {
    if (right === 6) right = 5;
    const rows = upward ? Array.from({ length: size }, (_, i) => size - 1 - i) : Array.from({ length: size }, (_, i) => i);
    for (const row of rows) {
      for (const col of [right, right - 1]) {
        if (reserved[row][col]) continue;
        if (bitIdx < bits.length) {
          matrix[row][col] = bits[bitIdx] ? 1 : 0;
          bitIdx++;
        }
      }
    }
    upward = !upward;
  }
}

function applyMask(matrix, reserved, size, maskId) {
  const maskFn = [
    (r, c) => (r + c) % 2 === 0,
    (r) => r % 2 === 0,
    (_, c) => c % 3 === 0,
    (r, c) => (r + c) % 3 === 0,
    (r, c) => (Math.floor(r / 2) + Math.floor(c / 3)) % 2 === 0,
    (r, c) => ((r * c) % 2 + (r * c) % 3) === 0,
    (r, c) => ((r * c) % 2 + (r * c) % 3) % 2 === 0,
    (r, c) => ((r + c) % 2 + (r * c) % 3) % 2 === 0
  ][maskId];

  for (let r = 0; r < size; r++) {
    for (let c = 0; c < size; c++) {
      if (!reserved[r][c] && maskFn(r, c)) {
        matrix[r][c] ^= 1;
      }
    }
  }
}

function writeFormatInfo(matrix, size, ecl, maskId) {
  const idx = ecl * 8 + maskId;
  const info = FORMAT_INFO_STRINGS[idx];
  for (let i = 0; i < 15; i++) {
    const bit = (info >> i) & 1;
    let r, c;
    if (i < 6) { r = i; c = 8; }
    else if (i < 8) { r = i + 1; c = 8; }
    else { r = size - 15 + i; c = 8; }
    matrix[r][c] = bit;

    if (i < 8) { r = 8; c = size - 1 - i; }
    else if (i < 9) { r = 8; c = 15 - i; }
    else { r = 8; c = 14 - i; }
    matrix[r][c] = bit;
  }
}

function writeVersionInfo(matrix, size, version) {
  if (version < 7) return;
  const info = VERSION_INFO_STRINGS[version];
  for (let i = 0; i < 18; i++) {
    const bit = (info >> i) & 1;
    const r = Math.floor(i / 3);
    const c = size - 11 + (i % 3);
    matrix[r][c] = bit;
    matrix[c][r] = bit;
  }
}

function calcPenalty(matrix, size) {
  let penalty = 0;
  // Rule 1: consecutive same-color modules
  for (let r = 0; r < size; r++) {
    let count = 1;
    for (let c = 1; c < size; c++) {
      if (matrix[r][c] === matrix[r][c - 1]) {
        count++;
        if (count === 5) penalty += 3;
        else if (count > 5) penalty += 1;
      } else count = 1;
    }
  }
  for (let c = 0; c < size; c++) {
    let count = 1;
    for (let r = 1; r < size; r++) {
      if (matrix[r][c] === matrix[r - 1][c]) {
        count++;
        if (count === 5) penalty += 3;
        else if (count > 5) penalty += 1;
      } else count = 1;
    }
  }
  // Rule 2: 2x2 blocks
  for (let r = 0; r < size - 1; r++) {
    for (let c = 0; c < size - 1; c++) {
      const v = matrix[r][c];
      if (v === matrix[r][c + 1] && v === matrix[r + 1][c] && v === matrix[r + 1][c + 1]) penalty += 3;
    }
  }
  return penalty;
}

function generateQR(text, ecl = 0) {
  const { version, dataBytes } = encodeData(text, ecl);
  const allBytes = interleaveBlocks(version, ecl, dataBytes);
  const bits = [];
  for (const b of allBytes) {
    for (let i = 7; i >= 0; i--) bits.push((b >> i) & 1);
  }
  const totalBits = version <= 1 ? 208 : (() => {
    const s = version * 4 + 17;
    let total = s * s;
    // subtract reserved modules (approximate, exact via matrix)
    return total;
  })();

  let bestMatrix = null;
  let bestPenalty = Infinity;

  for (let mask = 0; mask < 8; mask++) {
    const { matrix, reserved, size } = createMatrix(version);
    placeData(matrix, reserved, size, bits);
    applyMask(matrix, reserved, size, mask);
    writeFormatInfo(matrix, size, ecl, mask);
    writeVersionInfo(matrix, size, version);

    const penalty = calcPenalty(matrix, size);
    if (penalty < bestPenalty) {
      bestPenalty = penalty;
      bestMatrix = { matrix, size };
    }
  }

  return bestMatrix;
}

// --- Component ---

Component({
  properties: {
    text: { type: String, value: '' },
    size: { type: Number, value: 360 },
    colorDark: { type: String, value: '#000000' },
    colorLight: { type: String, value: '#ffffff' }
  },

  observers: {
    'text': function (val) {
      if (val) this.drawQR();
    }
  },

  lifetimes: {
    ready() {
      if (this.data.text) this.drawQR();
    }
  },

  methods: {
    drawQR() {
      const text = this.data.text;
      if (!text) return;

      let qr;
      try {
        qr = generateQR(text, 0);
      } catch (e) {
        console.error('QR generation failed:', e);
        return;
      }

      const query = this.createSelectorQuery();
      query.select('#qrcode-canvas').fields({ node: true, size: true }).exec((res) => {
        if (!res || !res[0] || !res[0].node) return;
        const canvas = res[0].node;
        const ctx = canvas.getContext('2d');
        const dpr = wx.getWindowInfo().pixelRatio || 2;
        const canvasWidth = res[0].width;
        const canvasHeight = res[0].height;
        canvas.width = canvasWidth * dpr;
        canvas.height = canvasHeight * dpr;
        ctx.scale(dpr, dpr);

        const { matrix, size: moduleCount } = qr;
        const quietZone = 2;
        const totalModules = moduleCount + quietZone * 2;
        const cellSize = canvasWidth / totalModules;

        ctx.fillStyle = this.data.colorLight;
        ctx.fillRect(0, 0, canvasWidth, canvasHeight);

        ctx.fillStyle = this.data.colorDark;
        for (let r = 0; r < moduleCount; r++) {
          for (let c = 0; c < moduleCount; c++) {
            if (matrix[r][c]) {
              ctx.fillRect(
                (c + quietZone) * cellSize,
                (r + quietZone) * cellSize,
                cellSize, cellSize
              );
            }
          }
        }

        this._canvas = canvas;
        this.triggerEvent('ready', { canvas });
      });
    },

    toTempFilePath(options = {}) {
      return new Promise((resolve, reject) => {
        if (!this._canvas) {
          reject(new Error('Canvas not ready'));
          return;
        }
        const dpr = wx.getWindowInfo().pixelRatio || 2;
        wx.canvasToTempFilePath({
          canvas: this._canvas,
          x: 0, y: 0,
          width: this._canvas.width,
          height: this._canvas.height,
          destWidth: this._canvas.width,
          destHeight: this._canvas.height,
          fileType: options.fileType || 'png',
          quality: options.quality || 1,
          success: (res) => resolve(res.tempFilePath),
          fail: reject
        }, this);
      });
    }
  }
});
