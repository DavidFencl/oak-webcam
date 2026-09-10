'use strict';
const $ = id => document.getElementById(id);
let token = new URLSearchParams(location.hash.slice(1)).get('token') || '';
let connected = false, previewURL = null, presets = [], defaultView = null;
const viewKeys = ["yaw", "pitch", "distance", "target", "fov"];
const isPointcloud = () => ["pointcloud", "pointcloud-depth"].includes($("preset").value);
function fillView(view) { if (view) for (const key of viewKeys) $("view-" + key).value = view[key]; }
if (token) { $('token').value = token; history.replaceState(null, '', location.pathname); }
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {...options.headers, Authorization: `Bearer ${token}`}});
  if (!response.ok) throw new Error((await response.json()).error || `HTTP ${response.status}`);
  return response;
}
function describe() {
  $('custom').hidden = $('preset').value !== 'custom';
  $('view-controls').hidden = !isPointcloud();
  $('switch').textContent = isPointcloud() ? 'Apply pipeline and fixed view' : 'Switch pipeline';
  const selected = presets.find(p => p.name === $('preset').value);
  $('description').textContent = selected ? (selected.name === 'custom' ? `${selected.description}. Output must match the USB mode above.` : `${selected.description}. Preset output: ${selected.width}×${selected.height}.`) : '';
}
async function refresh() {
  if (!connected) return;
  try {
    const status = await (await api('/api/status')).json();
    $('controls').hidden = false;
    $('phase').textContent = status.target ? `${status.phase}: ${status.target}` : `${status.phase}: ${status.preset || 'camera'}`;
    $('output').textContent = `USB ${status.usb.width}×${status.usb.height} · ${status.usb.fps} FPS mode`;
    $('error').textContent = status.error || '';
    if (!presets.length) {
      presets = status.presets;
      defaultView = status.default_view;
      fillView(status.target_view || status.view || defaultView);
      for (const p of presets) { const option = document.createElement('option'); option.value = p.name; option.textContent = p.name; $('preset').append(option); }
      $('preset').value = status.target || status.preset || presets[0].name;
      $('custom-path').value = status.target_path || status.custom_path || '';
      describe();
    }
    $('switch').disabled = ['preparing','starting','switching','rolling-back'].includes(status.phase);
    $('freshness').textContent = status.frame_age == null ? 'Waiting for an encoded camera frame' : `${status.frames} encoded frames · latest ${status.frame_age.toFixed(1)}s ago · preview updates once per second`;
    if (status.frame_age != null && status.frame_age < 5) {
      const image = await (await api('/api/preview.jpg')).blob();
      const previous = previewURL; previewURL = URL.createObjectURL(image);
      $('preview').src = previewURL; $('preview').hidden = false;
      if (previous) URL.revokeObjectURL(previous);
    } else { $('preview').hidden = true; }
  } catch (error) { $('error').textContent = error.message; $('controls').hidden = false; $('phase').textContent = 'Connection unavailable'; $('preview').hidden = true; }
}
$('connect').addEventListener('submit', async event => { event.preventDefault(); token = $('token').value.trim(); connected = true; await refresh(); });
$('preset').addEventListener('change', describe);
$('view-front').addEventListener('click', () => fillView({yaw: 0, pitch: 0, distance: 2, target: 2, fov: 70}));
$('view-angled').addEventListener('click', () => fillView(defaultView));
$('switch').addEventListener('click', async () => {
  $('switch').disabled = true;
  try {
    const body = {preset: $('preset').value};
    if (body.preset === 'custom') body.path = $('custom-path').value.trim();
    if (isPointcloud()) {
      body.view = {};
      for (const key of viewKeys) {
        const input = $('view-' + key);
        if (!input.value.trim() || !input.checkValidity()) throw new Error(`Enter a valid ${key} value`);
        body.view[key] = Number(input.value);
      }
    }
    await api('/api/preset', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)});
  }
  catch (error) { $('error').textContent = error.message; $('switch').disabled = false; return; }
  await refresh();
});
async function poll() { await refresh(); setTimeout(poll, 1000); }
connected = Boolean(token); poll();
