// 4K AI WORKSTATION — Electron ana süreci.
// Python arka ucunu (geliştirmede `uv run`, paketlenmiş uygulamada PyInstaller ikilisi) başlatır,
// sağlıklı olana kadar bekler ve tüm API çağrılarını IPC üzerinden ona aktarır.
const { app, BrowserWindow, ipcMain, shell, clipboard, dialog, Menu } = require('electron');
const { spawn } = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const net = require('node:net');
const path = require('node:path');

const ROOT = path.join(__dirname, '..');
const TOKEN = crypto.randomBytes(24).toString('hex');
const REQUEST_TIMEOUT_MS = 10 * 60 * 1000; // derin araştırma / fikir analizi uzun sürebilir

let backend = null;
let backendPort = null;
let backendLog = '';
let mainWindow = null;
let quitting = false;

function freePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on('error', reject);
    srv.listen(0, '127.0.0.1', () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

function backendCommand(port) {
  const args = ['--desktop-backend', '--port', String(port)];
  if (app.isPackaged) {
    const exe = process.platform === 'win32' ? '4k-backend.exe' : '4k-backend';
    return { cmd: path.join(process.resourcesPath, 'backend', exe), args, cwd: process.resourcesPath };
  }
  const home = process.env.HOME || process.env.USERPROFILE || '';
  const localUv = path.join(home, '.local', 'bin', process.platform === 'win32' ? 'uv.exe' : 'uv');
  const uv = fs.existsSync(localUv) ? localUv : 'uv';
  return { cmd: uv, args: ['run', '--quiet', '--project', ROOT, 'python', '-m', 'workstation', ...args], cwd: ROOT };
}

async function startBackend() {
  backendPort = await freePort();
  const { cmd, args, cwd } = backendCommand(backendPort);
  backend = spawn(cmd, args, {
    cwd,
    env: { ...process.env, FOURK_DESKTOP_TOKEN: TOKEN, PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8' },
    stdio: ['pipe', 'pipe', 'pipe'], // stdin açık kalır; uygulama ölürse arka uç EOF görüp kapanır
    windowsHide: true,
  });
  const keepLog = (chunk) => {
    backendLog = (backendLog + chunk.toString()).slice(-8000);
  };
  backend.stdout.on('data', keepLog);
  backend.stderr.on('data', keepLog);
  backend.on('exit', (code) => {
    backend = null;
    if (!quitting) {
      dialog.showErrorBox('4K AI WORKSTATION', `Arka uç beklenmedik şekilde kapandı (kod ${code}).\n\n${backendLog.slice(-2000)}`);
      app.quit();
    }
  });

  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    if (!backend) throw new Error(`Arka uç başlatılamadı.\n\n${backendLog.slice(-2000)}`);
    try {
      const r = await fetch(`http://127.0.0.1:${backendPort}/health`);
      if (r.ok) return;
    } catch {
      // henüz hazır değil
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  throw new Error(`Arka uç 60 sn içinde yanıt vermedi.\n\n${backendLog.slice(-2000)}`);
}

function stopBackend() {
  if (!backend) return;
  try {
    backend.stdin.end();
    backend.kill();
  } catch {
    // zaten kapanmış
  }
}

ipcMain.handle('api', async (_event, { method = 'GET', path: apiPath, body }) => {
  if (typeof apiPath !== 'string' || !apiPath.startsWith('/api/')) {
    return { ok: false, status: 400, data: { detail: 'Geçersiz yol' } };
  }
  try {
    const r = await fetch(`http://127.0.0.1:${backendPort}${apiPath}`, {
      method,
      headers: { 'Content-Type': 'application/json', 'X-4K-Token': TOKEN },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
    });
    const data = await r.json().catch(() => ({}));
    return { ok: r.ok, status: r.status, data };
  } catch (err) {
    return { ok: false, status: 0, data: { detail: `Arka uca ulaşılamadı: ${err.message}` } };
  }
});

ipcMain.handle('open-external', (_e, url) => {
  if (/^https?:\/\//.test(url)) shell.openExternal(url);
});
ipcMain.handle('open-path', (_e, p) => shell.openPath(String(p)));
ipcMain.handle('copy', (_e, text) => clipboard.writeText(String(text)));

// Duman testi: FOURK_SMOKE_SCREENSHOT=/yol/ekran.png ile başlatılırsa arayüzü yükler, her sekmenin
// ekran görüntüsünü alır ve kapanır (CI ve paket doğrulaması için; Linux CI'da xvfb-run ile).
const SMOKE = process.env.FOURK_SMOKE_SCREENSHOT;

async function runSmokeTest() {
  const wc = mainWindow.webContents;
  const views = ['desk', 'chat', 'radar', 'project', 'business', 'sync'];
  for (const view of views) {
    await wc.executeJavaScript(`document.querySelector('#nav button[data-view="${view}"]').click()`);
    await new Promise((r) => setTimeout(r, view === 'desk' ? 4000 : 1500));
    const img = await wc.capturePage();
    fs.writeFileSync(SMOKE.replace(/\.png$/, `-${view}.png`), img.toPNG());
  }
  const errors = await wc.executeJavaScript('document.querySelectorAll(".toast.error").length');
  console.log(`${errors ? 'SMOKE_FAIL' : 'SMOKE_OK'} views=${views.length} error_toasts=${errors}`);
  quitting = true;
  stopBackend();
  app.exit(errors ? 1 : 0);
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 960,
    minHeight: 640,
    title: '4K AI WORKSTATION',
    backgroundColor: '#0d1117',
    icon: path.join(__dirname, 'assets', 'icon.png'),
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  if (SMOKE) {
    mainWindow.webContents.on('console-message', (e) => console.log(`[renderer] ${e.message}`));
    mainWindow.webContents.once('did-finish-load', () => runSmokeTest().catch((err) => {
      console.error('SMOKE_FAIL', err);
      app.exit(1);
    }));
  }
  // Model çıktısındaki bağlantılar uygulama içinde değil, sistem tarayıcısında açılır.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//.test(url)) shell.openExternal(url);
    return { action: 'deny' };
  });
  mainWindow.webContents.on('will-navigate', (e, url) => {
    if (!url.startsWith('file://')) {
      e.preventDefault();
      if (/^https?:\/\//.test(url)) shell.openExternal(url);
    }
  });
}

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(async () => {
    Menu.setApplicationMenu(null);
    try {
      await startBackend();
    } catch (err) {
      dialog.showErrorBox('4K AI WORKSTATION', String(err.message || err));
      quitting = true;
      stopBackend();
      app.quit();
      return;
    }
    createWindow();
    app.on('activate', () => {
      if (BrowserWindow.getAllWindows().length === 0) createWindow();
    });
  });

  app.on('before-quit', () => {
    quitting = true;
    stopBackend();
  });
  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit();
  });
}
