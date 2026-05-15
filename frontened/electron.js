const { app, BrowserWindow, shell, dialog, Menu } = require('electron');
const path = require('path');

let mainWindow;

function createWindow() {
  // 创建浏览器窗口
  mainWindow = new BrowserWindow({
    width: 400,
    height: 200,
    show: true,
    resizable: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    },
    icon: path.join(__dirname, 'build', 'icon.ico'), // 应用图标
    title: '我的网页应用',
    center: true,
    minimizable: false,
    maximizable: false
  });

  // 加载本地HTML文件或直接打开网页
  mainWindow.loadFile(path.join(__dirname, 'build', 'index.html'));
  
  // 或者直接打开外部网页（推荐）
  // shell.openExternal('https://your-website.com');
  
  // 隐藏菜单栏
  Menu.setApplicationMenu(null);
  
  // 窗口准备好后显示
  mainWindow.once('ready-to-show', () => {
    // 可选：自动打开浏览器并关闭 Electron 窗口
    openBrowserAndClose();
  });

  mainWindow.on('closed', function () {
    mainWindow = null;
  });
}

function openBrowserAndClose() {
  const targetUrl = 'https://your-website.com'; // 替换为你的网址
  
  // 在默认浏览器中打开网页
  shell.openExternal(targetUrl).then(() => {
    console.log('成功在浏览器中打开网页');
    
    // 延迟关闭 Electron 窗口，让用户看到界面
    setTimeout(() => {
      if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.close();
      }
      app.quit();
    }, 2000);
    
  }).catch(err => {
    console.error('打开浏览器失败:', err);
    dialog.showErrorBox('打开失败', '无法打开默认浏览器，请手动访问: ' + targetUrl);
  });
}

// Electron 应用准备就绪
app.whenReady().then(createWindow);

// 所有窗口关闭时退出应用
app.on('window-all-closed', function () {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', function () {
  if (mainWindow === null) createWindow();
});