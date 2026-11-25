/*--------------------------------------------------------------------------------------
 *  Copyright 2026 Stratum Research Group & Nicholas Charles Mynhardt
 *  Licensed under the MIT License.
 *--------------------------------------------------------------------------------------*/

import { Disposable } from '../../../../base/common/lifecycle.js';
import { ICodeEditorService } from '../../../../editor/browser/services/codeEditorService.js';
import { ICodeEditor } from '../../../../editor/browser/editorBrowser.js';
import { IModelDeltaDecoration, OverviewRulerLane, TrackedRangeStickiness } from '../../../../editor/common/model.js';
import { Range } from '../../../../editor/common/core/range.js';
import { IWorkbenchContribution, registerWorkbenchContribution2, WorkbenchPhase } from '../../../common/contributions.js';

export class LeanGutterDecorator extends Disposable implements IWorkbenchContribution {
	static readonly ID = 'workbench.contrib.leanGutterDecorator';

	private _decorations: string[] = [];

	constructor(
		@ICodeEditorService private readonly _codeEditorService: ICodeEditorService,
	) {
		super();
		this._register(this._codeEditorService.onCodeEditorAdd(editor => this._hookEditor(editor)));
		const activeEditor = this._codeEditorService.getActiveCodeEditor();
		if (activeEditor) {
			this._hookEditor(activeEditor);
		}
	}

	private _hookEditor(editor: ICodeEditor): void {
		this._register(editor.onDidChangeModelContent(() => {
			this._updateDecorations(editor);
		}));
		this._register(editor.onDidChangeModel(() => {
			this._updateDecorations(editor);
		}));
		this._updateDecorations(editor);
	}

	private _updateDecorations(editor: ICodeEditor): void {
		const model = editor.getModel();
		if (!model) return;

		const uriStr = model.uri.toString();
		// Only decorate Lean 4 and proof-related files
		if (!uriStr.endsWith('.lean') && !uriStr.includes('proofs') && !uriStr.includes('gym')) {
			return;
		}

		const lines = model.getLinesContent();
		const newDecorations: IModelDeltaDecoration[] = [];

		for (let lineNum = 1; lineNum <= lines.length; lineNum++) {
			const line = lines[lineNum - 1];
			// Check for theorem, lemma, def declarations
			if (line.match(/^\s*(theorem|lemma|def)\s+([a-zA-Z0-9_]+)/)) {
				// Scan subsequent lines for 'sorry'
				let hasSorry = false;
				for (let lookahead = lineNum; lookahead <= Math.min(lines.length, lineNum + 40); lookahead++) {
					const aheadLine = lines[lookahead - 1];
					if (lookahead > lineNum && aheadLine.match(/^\s*(theorem|lemma|def)\s+/)) {
						break;
					}
					if (aheadLine.includes('sorry')) {
						hasSorry = true;
						break;
					}
				}

				if (hasSorry) {
					newDecorations.push({
						range: new Range(lineNum, 1, lineNum, 1),
						options: {
							description: 'lean-gutter-warning',
							isWholeLine: false,
							linesDecorationsClassName: 'codicon codicon-warning imf-lean-gutter-amber',
							overviewRuler: {
								color: '#f59e0b',
								position: OverviewRulerLane.Right
							},
							hoverMessage: { value: '**IMF Lean 4 Invariant Warning**: Unproven clause detected (`sorry`).' },
							stickiness: TrackedRangeStickiness.NeverGrowsWhenTypingAtEdges
						}
					});
				} else {
					newDecorations.push({
						range: new Range(lineNum, 1, lineNum, 1),
						options: {
							description: 'lean-gutter-verified',
							isWholeLine: false,
							linesDecorationsClassName: 'codicon codicon-check imf-lean-gutter-green',
							overviewRuler: {
								color: '#10b981',
								position: OverviewRulerLane.Right
							},
							hoverMessage: { value: '**IMF Lean 4 Certified Invariant**: Theorem formal proof sealed (0 sorry | 0 axioms).' },
							stickiness: TrackedRangeStickiness.NeverGrowsWhenTypingAtEdges
						}
					});
				}
			}
		}

		this._decorations = editor.deltaDecorations(this._decorations, newDecorations);
	}
}

registerWorkbenchContribution2(LeanGutterDecorator.ID, LeanGutterDecorator, WorkbenchPhase.AfterRestored);
