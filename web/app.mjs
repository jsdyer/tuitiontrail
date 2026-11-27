import { cleanLines } from './model.mjs';
const input = document.querySelector('#input');
const output = document.querySelector('#output');
const status = document.querySelector('#status');
const copy = document.querySelector('#copy');
function update() {
  const result = cleanLines(input.value);
  output.value = result.text;
  status.textContent = result.count
    ? `${result.count} unique ${result.count === 1 ? 'line' : 'lines'}. ${result.removed} ${result.removed === 1 ? 'duplicate' : 'duplicates'} removed.`
    : 'Paste one item per line or restore the example.';
  copy.disabled = result.count === 0;
}
input.addEventListener('input', update);
document.querySelector('#sample').addEventListener('click', () => {
  input.value = input.defaultValue;
  update();
});
document.querySelector('#clear').addEventListener('click', () => {
  input.value = '';
  update();
  input.focus();
});
if (navigator.clipboard && window.isSecureContext) {
  copy.hidden = false;
  copy.disabled = true;
  copy.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(output.value);
      status.textContent = 'Result copied.';
    } catch {
      output.focus();
      output.select();
      status.textContent = 'Copy was unavailable. The result is selected so you can copy it manually.';
    }
  });
}
if (input.value) update();
// Namespace future preference storage as coolcode:<tool-id>:<key>.
// Do not persist pasted text or uploads by default.
