const { app, BrowserWindow, ipcMain, Menu, Tray, nativeImage, screen } = require("electron");
const path = require("path");

let mainWindow;
let tray;

function createWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;

  mainWindow = new BrowserWindow({
    width: 360,
    height: 420,
    x: Math.max(0, width - 390),
    y: Math.max(0, height - 450),
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    hasShadow: false,
    backgroundColor: "#00000000",
    paintWhenInitiallyHidden: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false
    }
  });

  mainWindow.setAlwaysOnTop(true, "floating");
  mainWindow.setBackgroundColor("#00000000");
  mainWindow.loadFile(path.join(__dirname, "app", "index.html"));
}

function createTray() {
  tray = new Tray(nativeImage.createEmpty());
  tray.setToolTip("쿨 비서");
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: "쿨 비서 보이기", click: () => mainWindow?.show() },
    { label: "숨기기", click: () => mainWindow?.hide() },
    { type: "separator" },
    { label: "종료", click: () => app.quit() }
  ]));
}

app.commandLine.appendSwitch("disable-gpu-compositing");

app.whenReady().then(() => {
  createWindow();
  createTray();

  ipcMain.on("quit-app", () => app.quit());
  ipcMain.on("hide-app", () => mainWindow?.hide());

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
    else mainWindow?.show();
  });
});

app.on("window-all-closed", event => event.preventDefault());
