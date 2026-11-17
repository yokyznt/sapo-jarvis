const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');

const gradle = fs.readFileSync(path.join(__dirname, 'app', 'build.gradle.kts'), 'utf8');
const VERSION = (gradle.match(/versionName = "([^"]+)"/) || [])[1] || '0.0.0';
const ENTREGA = path.join(os.homedir(), 'Trabajos', 'APKs', 'Sapo-APK');
const PROPS = path.join(ENTREGA, 'llaves', 'keystore.properties');

const env = Object.assign({}, process.env);
const jdks = path.join(os.homedir(), '.jdks');
if (fs.existsSync(jdks)) {
    const jdk = fs.readdirSync(jdks).filter(d => /^jdk-(17|21)\./.test(d)).sort().pop();
    if (jdk) env.JAVA_HOME = path.join(jdks, jdk);
}
env.ANDROID_HOME = env.ANDROID_HOME || path.join(process.env.LOCALAPPDATA || '', 'Android', 'Sdk');
env.ANDROID_SDK_ROOT = env.ANDROID_HOME;

const firmado = fs.existsSync(PROPS);
if (firmado) env.SAPO_KEYSTORE_PROPS = PROPS;
else console.warn('Falta la llave de firma (' + PROPS + '); compilo debug.');
const tipo = firmado ? 'release' : 'debug';
const tarea = firmado ? 'assembleRelease' : 'assembleDebug';

const gw = path.join(__dirname, process.platform === 'win32' ? 'gradlew.bat' : 'gradlew');
const r = spawnSync(gw, [':app:' + tarea, '--console=plain', '-q'], { cwd: __dirname, env, stdio: 'inherit', shell: process.platform === 'win32' });
if (r.status !== 0) process.exit(r.status || 1);

fs.mkdirSync(ENTREGA, { recursive: true });
const origen = path.join(__dirname, 'app', 'build', 'outputs', 'apk', tipo, 'app-' + tipo + '.apk');
const destino = path.join(ENTREGA, 'Sapo-' + VERSION + (firmado ? '' : '-debug') + '.apk');
fs.copyFileSync(origen, destino);
console.log('Listo: ' + destino + ' (' + (fs.statSync(destino).size / 1048576).toFixed(1) + ' MB)');
