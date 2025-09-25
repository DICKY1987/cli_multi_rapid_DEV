import * as vscode from 'vscode';

export function openCockpitPanel(context: vscode.ExtensionContext) {
    const panel = vscode.window.createWebviewPanel(
        'cliMultiRapidCockpit',
        'CLI Multi-Rapid Cockpit',
        vscode.ViewColumn.One,
        {
            enableScripts: true,
            localResourceRoots: [vscode.Uri.joinPath(context.extensionUri, 'media')]
        }
    );

    const mediaUri = vscode.Uri.joinPath(context.extensionUri, 'media');
    const appJs = panel.webview.asWebviewUri(vscode.Uri.joinPath(mediaUri, 'app.js'));

    panel.webview.html = `<!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src ${panel.webview.cspSource} https:; script-src ${panel.webview.cspSource}; style-src ${panel.webview.cspSource} 'unsafe-inline';" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>CLI Multi-Rapid Cockpit</title>
      <style>body { font-family: var(--vscode-font-family); padding: 8px; }</style>
    </head>
    <body>
      <h2>Workflow Cockpit</h2>
      <div id="status">Connecting...</div>
      <pre id="log" style="background:#111;color:#ddd;padding:8px;max-height:40vh;overflow:auto"></pre>
      <script src="${appJs}"></script>
    </body>
    </html>`;

    return panel;
}

