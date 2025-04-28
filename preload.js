const { contextBridge, ipcRenderer } = require('electron');

contextBridge.expose({
    makeRequest: (options) => ipcRenderer.invoke('make-request', options),
});