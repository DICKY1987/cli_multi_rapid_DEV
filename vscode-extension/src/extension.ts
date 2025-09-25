import * as vscode from 'vscode';
import { openCockpitPanel } from './webview';
let extContext: vscode.ExtensionContext | undefined;

let webSocketClient: any;

export function activate(context: vscode.ExtensionContext) {
    console.log('CLI Multi-Rapid extension is now active!');
    extContext = context;

    // Register commands
    const commands = [
        vscode.commands.registerCommand('cliMultiRapid.openCockpit', openCockpit),
        vscode.commands.registerCommand('cliMultiRapid.startWorkflow', startWorkflow),
        vscode.commands.registerCommand('cliMultiRapid.runStreamComplete', runStreamComplete),
        vscode.commands.registerCommand('cliMultiRapid.estimateAICost', estimateAICost),
    ];

    commands.forEach(cmd => context.subscriptions.push(cmd));

    // Status bar item
    const statusBarItem = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Left,
        100
    );
    statusBarItem.text = "$(gear) CLI Multi-Rapid";
    statusBarItem.command = 'cliMultiRapid.openCockpit';
    statusBarItem.tooltip = 'Open CLI Multi-Rapid Workflow Cockpit';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);
}

async function openCockpit() {
    try {
        if (extContext) {
            const panel = openCockpitPanel(extContext);
            const cfg = vscode.workspace.getConfiguration('cliMultiRapid');
            const serverUrl = cfg.get<string>('serverUrl', 'http://localhost:8000');
            const wsUrl = serverUrl.replace(/^http(s?):\/\//, 'ws$1://') + '/ws';
            panel.webview.postMessage({ type: 'config', serverUrl, wsUrl });
        } else {
            vscode.window.showInformationMessage('CLI Multi-Rapid Cockpit (context unavailable)');
        }
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to open cockpit: ${error}`);
    }
}

async function startWorkflow() {
    try {
        const description = await vscode.window.showInputBox({
            prompt: 'Describe the workflow task',
            placeHolder: 'e.g., Refactor this function to use async/await'
        });

        if (!description) {
            return;
        }

        vscode.window.showInformationMessage(`Workflow started: ${description}`);
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to start workflow: ${error}`);
    }
}

async function runStreamComplete() {
    try {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            vscode.window.showErrorMessage('No workspace folder open');
            return;
        }
        const root = workspaceFolders[0].uri.fsPath;
        const term = vscode.window.createTerminal({ name: 'CLI Multi-Rapid: stream-complete', cwd: root });
        const isWindows = process.platform === 'win32';
        const cmd = isWindows
            ? 'set PYTHONPATH=src&& python -m workflows.orchestrator run-stream stream-complete'
            : 'PYTHONPATH=src python -m workflows.orchestrator run-stream stream-complete';
        term.show(true);
        term.sendText(cmd);
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to run stream: ${error}`);
    }
}

async function estimateAICost() {
    try {
        const workspaceFolders = vscode.workspace.workspaceFolders;
        if (!workspaceFolders || workspaceFolders.length === 0) {
            vscode.window.showErrorMessage('No workspace folder open');
            return;
        }
        const root = workspaceFolders[0].uri.fsPath;
        const term = vscode.window.createTerminal({ name: 'CLI Multi-Rapid: AI Cost', cwd: root });
        const isWindows = process.platform === 'win32';
        const cmd = isWindows
            ? 'set PYTHONPATH=src&& python -c "from cli_multi_rapid.adapters.cost_estimator import CostEstimatorAdapter; step={\'actor\':\'cost_estimator\', \'with\':{\'workflow\':\'.ai/workflows/AI_WORKFLOW_DEMO.yaml\'}, \'emits\':[\'artifacts/ai-cost.json\']}; print(CostEstimatorAdapter().execute(step))"'
            : 'PYTHONPATH=src python -c "from cli_multi_rapid.adapters.cost_estimator import CostEstimatorAdapter; step={\'actor\':\'cost_estimator\', \'with\':{\'workflow\':\'.ai/workflows/AI_WORKFLOW_DEMO.yaml\'}, \'emits\':[\'artifacts/ai-cost.json\']}; print(CostEstimatorAdapter().execute(step))"';
        term.show(true);
        term.sendText(cmd);
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to estimate cost: ${error}`);
    }
}

export function deactivate() {
    if (webSocketClient) {
        // webSocketClient.disconnect();
    }
}
