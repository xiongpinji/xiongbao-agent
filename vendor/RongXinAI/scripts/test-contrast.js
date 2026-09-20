function luminance(hex) {
  const clean = hex.replace('#', '');
  const rgb = [
    parseInt(clean.slice(0, 2), 16),
    parseInt(clean.slice(2, 4), 16),
    parseInt(clean.slice(4, 6), 16),
  ].map((v) => {
    const c = v / 255;
    return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  });
  return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
}
function contrast(a, b) {
  const v = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (v[0] + 0.05) / (v[1] + 0.05);
}

console.log('#1A1208 on #8A6508:', contrast('#1A1208', '#8A6508').toFixed(2));
console.log('#1A1208 on #FFC107:', contrast('#1A1208', '#FFC107').toFixed(2));
console.log('#FFFFFF on #8A6508:', contrast('#FFFFFF', '#8A6508').toFixed(2));
console.log('#1A1208 on #6E5224:', contrast('#1A1208', '#6E5224').toFixed(2)); // antiqueGold
console.log('#1A1208 on #5C4416:', contrast('#1A1208', '#5C4416').toFixed(2)); // darker gold
