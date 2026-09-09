'use strict';
const $ = id => document.getElementById(id);
let current, dirty = false, saving = false;
const numbers = ['file_gb','memory_mb','max_connections','max_payload_kb'];
function show() {
  if (!$('tls').checked) $('verify_clients').checked = false;
  $('tls-fields').hidden = !$('tls').checked;
  $('ca-field').hidden = !$('verify_clients').checked;
  $('token-fields').hidden = $('auth_mode').value !== 'token';
  $('users-fields').hidden = $('auth_mode').value !== 'users';
  $('review').textContent = `${$('tls').checked ? 'Encrypted TLS' : 'Unencrypted local TCP'} · ${$('auth_mode').value === 'token' ? 'Shared token' : 'Individual users'} · ${$('file_gb').value} GiB file storage. Use the HA Network port (4222 by default).`;
  $('save').disabled = saving || !current || !$('confirm').checked;
}
function field(label, kind, value, key) {
  const l = document.createElement('label'); l.textContent = label;
  const input = document.createElement(kind === 'textarea' ? 'textarea' : 'input');
  if(kind !== 'textarea') input.type = kind;
  input.dataset.key = key; input.value = value; input.autocomplete = kind === 'password' ? 'new-password' : 'off';
  if(kind === 'password') input.placeholder = 'Blank keeps an existing password';
  l.append(input); return l;
}
function addUser(user = {name:'',password:'',publish:[],subscribe:[]}) {
  const card = document.createElement('div'); card.className = 'user';
  const head = document.createElement('div'); head.className = 'user-head';
  const title = document.createElement('strong'); title.textContent = 'Client access';
  const remove = document.createElement('button'); remove.type = 'button'; remove.className = 'secondary'; remove.textContent = 'Remove';
  remove.onclick = () => {card.remove();dirty = true;}; head.append(title,remove); card.append(head);
  card.append(field('Username','text',user.name,'name'),field('Password','password','','password'),field('Can publish · one subject per line','textarea',user.publish.join('\n'),'publish'),field('Can subscribe · one subject per line','textarea',user.subscribe.join('\n'),'subscribe'));
  $('users').append(card);
}
function fill(state) {
  current = state.config;
  $('health').textContent = state.broker_running ? '● Server running' : 'Server stopped';
  $('security').textContent = state.tls_active ? 'TLS active' : 'Traffic is not encrypted';
  $('cert-status').textContent = state.certificate_files.length ? `${state.certificate_files.length} certificate/key files discovered in HA /ssl. The pair and expiry are checked when you apply.` : 'No certificate files found in HA /ssl. Add the HA certificate and private key before enabling TLS.';
  ['cert_file','key_file','client_ca'].forEach(key => {
    $(key).replaceChildren();
    const names = [...new Set([current[key], ...state.certificate_files])];
    names.forEach(name => {const option = document.createElement('option');option.value=name;option.textContent=name || 'Select a file';$(key).append(option);});
    $(key).value=current[key];
  });
  ['tls','verify_clients'].forEach(key => $(key).checked=current[key]);
  $('auth_mode').value=current.auth_mode; $('token').value='';
  numbers.forEach(key => $(key).value=current[key]);
  $('users').replaceChildren();current.users.forEach(addUser);
  $('confirm').checked=false;dirty=false;show();
}
async function refresh() {
  if(saving) return;
  if(dirty && !window.confirm('Discard unsaved changes and refresh discovery?')) return;
  try {const r=await fetch('./api/state');if(!r.ok)throw Error('Open this page from Home Assistant.');fill(await r.json());$('message').textContent='';}
  catch(e){$('message').textContent=e.message;$('message').className='error';}
}
$('settings').addEventListener('input',()=>{dirty=true;show();});
$('settings').addEventListener('change',show);
$('add-user').onclick=()=>{addUser();dirty=true;};$('refresh').onclick=refresh;
$('settings').onsubmit=async e=>{
  e.preventDefault();if(!current || saving)return;
  const cfg={...current}; numbers.forEach(k=>cfg[k]=Number($(k).value));
  ['tls','verify_clients'].forEach(k=>cfg[k]=$(k).checked);
  ['auth_mode','token','cert_file','key_file','client_ca'].forEach(k=>cfg[k]=$(k).value);
  cfg.users=[...$('users').children].map(card=>Object.fromEntries([...card.querySelectorAll('[data-key]')].map(input=>[input.dataset.key,['publish','subscribe'].includes(input.dataset.key)?input.value.split('\n').map(s=>s.trim()).filter(Boolean):input.value])));
  saving=true; $('settings').querySelectorAll('input,select,textarea,button').forEach(el=>el.disabled=true);
  $('save').disabled=true;$('message').className='';$('message').textContent='Validating and applying…';
  try{const r=await fetch('./api/config',{method:'POST',headers:{'Content-Type':'application/json','X-NATS-Config':'1'},body:JSON.stringify(cfg)});const result=await r.json();if(!r.ok)throw Error(result.error);fill(result);$('message').textContent='Applied. NATS is running with these settings.';}
  catch(error){$('message').textContent=error.message;$('message').className='error';}
  finally{saving=false;$('settings').querySelectorAll('input,select,textarea,button').forEach(el=>el.disabled=false);show();}
};
window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
refresh();
