// Renderer'a yalnızca dar ve tip güvenli bir köprü açılır; Node erişimi yoktur.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('fourk', {
  api: (method, path, body) => ipcRenderer.invoke('api', { method, path, body }),
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  openPath: (p) => ipcRenderer.invoke('open-path', p),
  copy: (text) => ipcRenderer.invoke('copy', text),
  platform: process.platform,
});
