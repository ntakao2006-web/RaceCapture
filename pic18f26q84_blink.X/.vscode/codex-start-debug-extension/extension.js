const vscode = require('vscode');

async function activate() {
  const projectUri = vscode.Uri.file(
    'C:\\Users\\lintaroh\\Documents\\RaceCapture\\pic18f26q84_blink.X'
  );
  let folder = vscode.workspace.workspaceFolders?.find(
    (item) => item.uri.fsPath === projectUri.fsPath
  );
  if (!folder) {
    vscode.workspace.updateWorkspaceFolders(0, 0, {
      uri: projectUri,
      name: 'pic18f26q84_blink.X'
    });
    await new Promise((resolve) => setTimeout(resolve, 3000));
    folder = vscode.workspace.workspaceFolders?.find(
      (item) => item.uri.fsPath === projectUri.fsPath
    );
  }
  if (!folder) {
    throw new Error('[Codex MPLAB Starter] Could not open target workspace.');
  }

  await new Promise((resolve) => setTimeout(resolve, 5000));
  const started = await vscode.debug.startDebugging(
    folder,
    'PIC18F26Q84 UARTテストを書き込む'
  );
  console.log(`[Codex MPLAB Starter] startDebugging returned ${started}.`);
}

function deactivate() {}

module.exports = { activate, deactivate };
