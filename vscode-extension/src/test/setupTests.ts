// Jest setup file for VS Code extension tests

// Mock VS Code API
const mockVSCode = {
    commands: {
        registerCommand: jest.fn(),
    },
    window: {
        createStatusBarItem: jest.fn(() => ({
            text: '',
            command: '',
            tooltip: '',
            show: jest.fn(),
        })),
        showInformationMessage: jest.fn(),
        showErrorMessage: jest.fn(),
        showInputBox: jest.fn(),
    },
    StatusBarAlignment: {
        Left: 1,
        Right: 2,
    },
};

// Mock the vscode module
jest.mock('vscode', () => mockVSCode, { virtual: true });

export default mockVSCode;