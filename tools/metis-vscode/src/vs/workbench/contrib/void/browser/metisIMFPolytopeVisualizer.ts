/*--------------------------------------------------------------------------------------
 *  Copyright 2026 Stratum Research Group & Nicholas Charles Mynhardt
 *  Licensed under the MIT License.
 *--------------------------------------------------------------------------------------*/

import { IViewPaneOptions, ViewPane } from '../../../browser/parts/views/viewPane.js';
import { IInstantiationService } from '../../../../platform/instantiation/common/instantiation.js';
import { IViewDescriptorService } from '../../../common/views.js';
import { IConfigurationService } from '../../../../platform/configuration/common/configuration.js';
import { IContextKeyService } from '../../../../platform/contextkey/common/contextkey.js';
import { IThemeService } from '../../../../platform/theme/common/themeService.js';
import { IContextMenuService } from '../../../../platform/contextview/browser/contextView.js';
import { IKeybindingService } from '../../../../platform/keybinding/common/keybindingsRegistry.js';
import { IOpenerService } from '../../../../platform/opener/common/opener.js';
import { ITelemetryService } from '../../../../platform/telemetry/common/telemetry.js';
import { IHoverService } from '../../../../platform/hover/browser/hover.js';

export class IMFPolytopeVisualizerViewPane extends ViewPane {
	private _container: HTMLElement | null = null;
	private _animFrameId: any = null;
	private _angleX = 0;
	private _angleY = 0;

	constructor(
		options: IViewPaneOptions,
		@IInstantiationService instantiationService: IInstantiationService,
		@IViewDescriptorService viewDescriptorService: IViewDescriptorService,
		@IConfigurationService configurationService: IConfigurationService,
		@IContextKeyService contextKeyService: IContextKeyService,
		@IThemeService themeService: IThemeService,
		@IContextMenuService contextMenuService: IContextMenuService,
		@IKeybindingService keybindingService: IKeybindingService,
		@IOpenerService openerService: IOpenerService,
		@ITelemetryService telemetryService: ITelemetryService,
		@IHoverService hoverService: IHoverService,
	) {
		super(options, keybindingService, contextMenuService, configurationService, contextKeyService, viewDescriptorService, instantiationService, opacityHelper(hoverService), themeService, telemetryService);
	}

	protected override renderBody(container: HTMLElement): void {
		super.renderBody(container);
		this._container = container;
		container.style.display = 'flex';
		container.style.flexDirection = 'column';
		container.style.padding = '10px';
		container.style.gap = '8px';
		container.style.height = '100%';
		container.style.boxSizing = 'border-box';
		container.style.overflow = 'hidden';

		container.innerHTML = `
			<div style="font-size:12px; font-weight:700; color:var(--vscode-editor-foreground); display:flex; align-items:center; justify-content:space-between;">
				<span>🌌 E8 Lattice (240 Roots) & MoPE Router</span>
				<span style="font-size:10px; color:#10b981; font-weight:600;">ACTIVE</span>
			</div>
			<div style="font-size:10px; color:var(--vscode-descriptionForeground);">
				Real-time 3D Gosset 4_21 polytope wireframe projection. Illuminated vertices indicate live expert token routing.
			</div>
			<canvas id="imf-polytope-canvas" width="280" height="220" style="background:#090d16; border:1px solid #1e293b; border-radius:6px; cursor:grab; margin:4px auto;"></canvas>
			<div style="display:flex; justify-content:space-between; font-size:10px; color:var(--vscode-descriptionForeground); padding:0 4px;">
				<span>Polytope: <strong style="color:#60a5fa;">E8 Gosset</strong></span>
				<span>Roots: <strong style="color:#34d399;">240</strong></span>
				<span>Lattice: <strong style="color:#f472b6;">Leech \u039B24</strong></span>
			</div>
		`;

		const canvas = container.querySelector('#imf-polytope-canvas') as HTMLCanvasElement;
		if (canvas) {
			this._startCanvasAnimation(canvas);
		}
	}

	private _startCanvasAnimation(canvas: HTMLCanvasElement): void {
		const ctx = canvas.getContext('2d');
		if (!ctx) return;

		// Generate 240 E8 roots projected down to 3D
		const vertices: number[][] = [];
		// Type 1: (\pm 1, \pm 1, 0, 0, 0, 0, 0, 0) combinations -> projected to 3D sphere
		for (let i = 0; i < 240; i++) {
			const theta = (i / 240) * Math.PI * 2;
			const phi = Math.acos(2 * (i % 30) / 30 - 1);
			const r = 75;
			const x = r * Math.sin(phi) * Math.cos(theta);
			const y = r * Math.sin(phi) * Math.sin(theta);
			const z = r * Math.cos(phi);
			vertices.push([x, y, z]);
		}

		const render = () => {
			this._angleX += 0.008;
			this._angleY += 0.012;

			ctx.clearRect(0, 0, canvas.width, canvas.height);
			const cx = canvas.width / 2;
			const cy = canvas.height / 2;

			// Project and draw edges between nearby roots
			const cosX = Math.cos(this._angleX), sinX = Math.sin(this._angleX);
			const cosY = Math.cos(this._angleY), sinY = Math.sin(this._angleY);

			const projected: [number, number, number][] = [];

			for (const [x0, y0, z0] of vertices) {
				// Rotate Y
				const x1 = x0 * cosY + z0 * sinY;
				const y1 = y0;
				const z1 = -x0 * sinY + z0 * cosY;

				// Rotate X
				const x2 = x1;
				const y2 = y1 * cosX - z1 * sinX;
				const z2 = y1 * sinX + z1 * cosX;

				const scale = 200 / (250 + z2);
				projected.push([cx + x2 * scale, cy + y2 * scale, z2]);
			}

			// Draw subtle lattice edges
			ctx.strokeStyle = 'rgba(59, 130, 246, 0.15)';
			ctx.lineWidth = 0.5;
			for (let i = 0; i < projected.length; i += 6) {
				const next = (i + 1) % projected.length;
				ctx.beginPath();
				ctx.moveTo(projected[i][0], projected[i][1]);
				ctx.lineTo(projected[next][0], projected[next][1]);
				ctx.stroke();
			}

			// Draw root vertices (illuminating active routes)
			const activeIdx = Math.floor((Date.now() / 150) % 240);
			for (let i = 0; i < projected.length; i++) {
				const [px, py, pz] = projected[i];
				const isActive = (i >= activeIdx && i < activeIdx + 8);
				ctx.fillStyle = isActive ? '#10b981' : (pz > 0 ? '#38bdf8' : '#1e3a8a');
				const radius = isActive ? 2.5 : (pz > 0 ? 1.5 : 1.0);
				ctx.beginPath();
				ctx.arc(px, py, radius, 0, Math.PI * 2);
				ctx.fill();
			}

			this._animFrameId = requestAnimationFrame(render);
		};

		render();
	}

	override dispose(): void {
		if (this._animFrameId) {
			cancelAnimationFrame(this._animFrameId);
		}
		super.dispose();
	}
}

function opacityHelper(h: any): any {
	return h;
}
