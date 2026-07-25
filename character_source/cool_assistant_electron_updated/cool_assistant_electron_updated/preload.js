const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("desktopAPI", {
  quit: () => ipcRenderer.send("quit-app"),
  hide: () => ipcRenderer.send("hide-app")
});
