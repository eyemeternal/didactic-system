const pick = document.querySelector('#profiles');
const button = document.querySelector('#action');
const statusLine = document.querySelector('#status');
const log = document.querySelector('#log');
const fields = document.querySelector('#credentials');
const username = document.querySelector('#username');
const password = document.querySelector('#password');
let credentialProfile;
let items = [], busy = false, reading = false, last = '';
function record(text) {
  if (text !== last) log.textContent = new Date().toLocaleTimeString() + '  ' + text + '\n' + log.textContent.slice(0, 16000);
  last = text;
}
function render() {
  const item = items.find(p => p.id === pick.value);
  fields.hidden = !item || item.pending || item.active;
  if (credentialProfile !== item?.id || fields.hidden) {
    username.value = password.value = '';
    credentialProfile = item?.id;
  }
  button.disabled = !item || busy || reading;
  button.textContent = item?.pending ? 'Import profile' : item?.active ? 'Disconnect' : 'Connect';
  statusLine.textContent = item?.pending ? 'Ready to import' : item ? (item.active ? 'Connected' : 'Disconnected') : 'Place an .ovpn file in imports/ to begin.';
  record(item ? item.name + ' · ' + statusLine.textContent : statusLine.textContent);
}
async function refresh() {
  if (busy || reading) return;
  reading = true;
  try {
    const response = await fetch('/api/profiles');
    const data = await response.json();
    if (!response.ok) throw Error(data);
    const selected = pick.value;
    const previous = items.find(p => p.id === selected);
    items = data;
    pick.replaceChildren(...items.map(p => new Option(p.name, p.id)));
    if (items.some(p => p.id === selected)) pick.value = selected;
    else if (previous?.pending) {
      const imported = items.find(p => !p.pending && p.name === previous.name);
      if (imported) pick.value = imported.id;
    }
    reading = false;
    render();
  } catch (error) {
    fields.hidden = true;
    username.value = password.value = "";
    items = [];
    pick.replaceChildren();
    button.disabled = true;
    statusLine.textContent = error.message;
    record(error.message);
  } finally { reading = false; }
}
pick.onchange = render;
button.onclick = async () => {
  if (busy || reading) return;
  const item = items.find(p => p.id === pick.value);
  if (!item) return;
  busy = button.disabled = pick.disabled = true;
  const action = item.pending ? 'import' : item.active ? 'disconnect' : 'connect';
  statusLine.textContent = item.pending ? 'Importing…' : item.active ? 'Disconnecting…' : 'Connecting…';
  try {
    const options = {method: 'POST'};
    if (action === 'connect') {
      options.headers = {'Content-Type': 'application/json'};
      options.body = JSON.stringify({username: username.value, password: password.value});
      password.value = '';
    }
    const result = await fetch('/api/profiles/' + encodeURIComponent(item.id) + '/' + action, options);
    record(await result.json());
  } catch (error) { record(error.message); }
  busy = pick.disabled = false;
  await refresh();
};
refresh();
setInterval(refresh, 4000);
