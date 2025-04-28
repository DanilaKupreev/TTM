const { app, BrowserWindow, ipcMain } = require('electron');
const https = require('https'); // Или http, если твой сервер не HTTPS
const path = require('path');

async function makeRequest(event, options) {
    return new Promise((resolve, reject) => {
        const req = https.request(options, (res) => { // Или http.request
            let data = '';

            res.on('data', (chunk) => {
                data += chunk;
            });

            res.on('end', () => {
                resolve({
                    statusCode: res.statusCode,
                    headers: res.headers,
                    data,
                });
            });
        });

        req.on('error', (error) => {
            reject(error);
        });

        if (options.body) {
            req.write(options.body);
        }

        req.end();
    });
}

function createWindow() {
    const mainWindow = new BrowserWindow({
        width: 800,
        height: 600,
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            nodeIntegration: true,
            contextIsolation: false
        }
    });

    mainWindow.loadURL('http://172.17.16.194:8000/chat/'); // Замени на URL твоего Django-сервера

    //  mainWindow.webContents.openDevTools() // Открывает DevTools

}

app.whenReady().then(() => {
    createWindow();

    app.on('activate', function() {
        if (BrowserWindow.getAllWindows().length === 0) createWindow()
    })

    ipcMain.on('window-all-closed', function() {
        if (process.platform !== 'darwin') app.quit()
    })

    //  Пример получения событий из веб-приложения (через preload.js)
    ipcMain.on('ping', () => {
        console.log('pong')
    })

    //  Пример мигания иконки (только для macOS)
    ipcMain.on('flash-frame', () => {
        app.dock.bounce('informational') // Подпрыгивание иконки (macOS)
        // mainWindow.flashFrame(true); // Мигание рамки окна (Windows)
    })

    ipcMain.handle('make-request', async (event, options) => {
        try {
            const response = await makeRequest(event, options);
            return response;
        } catch (error) {
            console.error("Произошла ошибка при выполнении запроса:", error);
            throw error; // Перебрасываем ошибку обратно в preload.js
        }
    });
});