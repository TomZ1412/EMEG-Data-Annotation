const { app, BrowserWindow, dialog, shell } = require('electron');
const path = require('path');
const express = require('express');
const fs = require('fs');

// 判断是否为开发环境
const isDev = !app.isPackaged;

function getStaticPath() {
  if (isDev) {
    return path.join(__dirname, 'frontened', 'dist');
  } else {
    return path.join(process.resourcesPath, 'frontened', 'dist');
  }
}

function createServer() {
  return new Promise((resolve, reject) => {
    const server = express();
    const staticPath = getStaticPath();
    
    console.log('Static path:', staticPath);
    
    // 检查静态文件是否存在
    if (!fs.existsSync(staticPath)) {
      const error = `Static files not found at: ${staticPath}`;
      console.error(error);
      dialog.showErrorBox('启动错误', `找不到前端文件: ${staticPath}`);
      reject(new Error(error));
      return;
    }
    
    // 静态文件服务
    server.use(express.static(staticPath));
    
    // 修复路由：使用正确的通配符语法
    server.get('/', (req, res) => {
      res.sendFile(path.join(staticPath, 'index.html'));
    });
    
    const FIXED_PORT = 5173;
    // 使用随机端口避免冲突
    const serverInstance = server.listen(FIXED_PORT, () => {
      console.log(`Server running on port ${FIXED_PORT}`);
      resolve({ server: serverInstance, port: FIXED_PORT });
    });
    
    serverInstance.on('error', (err) => {
      console.error('Server error:', err);
      reject(err);
    });
  });
}

function createWindow(port) {
  const win = new BrowserWindow({
    width: 1280,
    height: 800,
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    }
  });
  
  win.once('ready-to-show', () => {
    win.show();
    win.focus();
  });
  
  const url = `http://localhost:${port}`;
  console.log('Loading URL:', url);
  
  win.loadURL(url).catch(err => {
    console.error('Failed to load URL:', err);
    dialog.showErrorBox('加载失败', `无法加载页面: ${err.message}`);
  });
}

app.whenReady().then(async () => {
  try {
    const { port } = await createServer();
    const url = `http://localhost:${port}`;

    await shell.openExternal(url); // 在系统默认浏览器打开
    // createWindow(port);
  } catch (error) {
    console.error('Failed to start app:', error);
    dialog.showErrorBox('启动失败', `应用启动失败: ${error.message}`);
    app.quit();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});