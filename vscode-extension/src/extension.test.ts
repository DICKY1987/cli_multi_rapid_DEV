import { activate, deactivate } from './extension';
import mockVSCode from './test/setupTests';

describe('CLI Multi-Rapid Extension', () => {
    let mockContext: any;

    beforeEach(() => {
        mockContext = {
            subscriptions: [],
        };
        jest.clearAllMocks();
    });

    test('should activate extension and register commands', () => {
        activate(mockContext);

        // Verify commands were registered
        expect(mockVSCode.commands.registerCommand).toHaveBeenCalledWith(
            'cliMultiRapid.openCockpit',
            expect.any(Function)
        );
        expect(mockVSCode.commands.registerCommand).toHaveBeenCalledWith(
            'cliMultiRapid.startWorkflow',
            expect.any(Function)
        );

        // Verify status bar item was created
        expect(mockVSCode.window.createStatusBarItem).toHaveBeenCalled();

        // Verify subscriptions were added to context
        expect(mockContext.subscriptions.length).toBeGreaterThan(0);
    });

    test('should handle openCockpit command', async () => {
        activate(mockContext);

        // Get the registered command handler
        const openCockpitCall = mockVSCode.commands.registerCommand.mock.calls
            .find(call => call[0] === 'cliMultiRapid.openCockpit');
        const openCockpitHandler = openCockpitCall[1];

        // Execute the command
        await openCockpitHandler();

        // Verify information message was shown
        expect(mockVSCode.window.showInformationMessage).toHaveBeenCalledWith(
            'Opening CLI Multi-Rapid Workflow Cockpit...'
        );
    });

    test('should handle startWorkflow command with user input', async () => {
        activate(mockContext);

        // Mock user input
        mockVSCode.window.showInputBox.mockResolvedValue('Test workflow description');

        // Get the registered command handler
        const startWorkflowCall = mockVSCode.commands.registerCommand.mock.calls
            .find(call => call[0] === 'cliMultiRapid.startWorkflow');
        const startWorkflowHandler = startWorkflowCall[1];

        // Execute the command
        await startWorkflowHandler();

        // Verify input box was shown
        expect(mockVSCode.window.showInputBox).toHaveBeenCalledWith({
            prompt: 'Describe the workflow task',
            placeHolder: 'e.g., Refactor this function to use async/await'
        });

        // Verify success message was shown
        expect(mockVSCode.window.showInformationMessage).toHaveBeenCalledWith(
            'Workflow started: Test workflow description'
        );
    });

    test('should handle startWorkflow command with no user input', async () => {
        activate(mockContext);

        // Mock no user input
        mockVSCode.window.showInputBox.mockResolvedValue(undefined);

        // Get the registered command handler
        const startWorkflowCall = mockVSCode.commands.registerCommand.mock.calls
            .find(call => call[0] === 'cliMultiRapid.startWorkflow');
        const startWorkflowHandler = startWorkflowCall[1];

        // Execute the command
        await startWorkflowHandler();

        // Verify only input box was shown, no workflow started message
        expect(mockVSCode.window.showInputBox).toHaveBeenCalled();
        expect(mockVSCode.window.showInformationMessage).not.toHaveBeenCalledWith(
            expect.stringMatching(/^Workflow started:/)
        );
    });

    test('should handle errors in commands gracefully', async () => {
        activate(mockContext);

        // Mock error in showInputBox
        mockVSCode.window.showInputBox.mockRejectedValue(new Error('Test error'));

        // Get the registered command handler
        const startWorkflowCall = mockVSCode.commands.registerCommand.mock.calls
            .find(call => call[0] === 'cliMultiRapid.startWorkflow');
        const startWorkflowHandler = startWorkflowCall[1];

        // Execute the command
        await startWorkflowHandler();

        // Verify error message was shown
        expect(mockVSCode.window.showErrorMessage).toHaveBeenCalledWith(
            'Failed to start workflow: Error: Test error'
        );
    });

    test('should deactivate extension cleanly', () => {
        activate(mockContext);

        // Should not throw
        expect(() => deactivate()).not.toThrow();
    });
});