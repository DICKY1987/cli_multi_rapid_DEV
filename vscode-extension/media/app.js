(function(){
  const statusEl = document.getElementById('status');
  const logEl = document.getElementById('log');
  let ws;

  function log(msg){
    const line = `[${new Date().toISOString()}] ${msg}`;
    logEl.textContent += line + "\n";
    logEl.scrollTop = logEl.scrollHeight;
  }

  function connect(wsUrl){
    try {
      ws = new WebSocket(wsUrl);
      ws.onopen = () => {
        statusEl.textContent = `Connected: ${wsUrl}`;
        log('WebSocket connected');
      };
      ws.onmessage = (ev) => {
        log(`evt: ${ev.data}`);
      };
      ws.onclose = () => {
        statusEl.textContent = 'Disconnected';
        log('WebSocket disconnected');
      };
      ws.onerror = (e) => {
        log('WebSocket error');
      };
    } catch (e) {
      log(`Failed to connect WS: ${e}`);
    }
  }

  window.addEventListener('message', (event) => {
    const msg = event.data || {};
    if (msg.type === 'config') {
      const wsUrl = msg.wsUrl || 'ws://localhost:8000/ws';
      log(`Config received; connecting to ${wsUrl}`);
      connect(wsUrl);
    }
  });

  statusEl.textContent = 'Ready';
  log('Cockpit loaded');
})();
