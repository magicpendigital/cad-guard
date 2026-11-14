// Review probes only. No server, external API, npm installation, or customer data.
// Node's built-in TypeScript stripping is used on temporary in-memory copies.
import fs from 'node:fs';
import path from 'node:path';
import {stripTypeScriptTypes} from 'node:module';

const root = process.cwd();
const dir = path.join(root, 'docs/reviews/2026-11-07-draff');
async function load(name, adjust = s => s) {
  let source = fs.readFileSync(path.join(root, 'Draff/src', name + '.ts'), 'utf8');
  source = adjust(source);
  const js = stripTypeScriptTypes(source, {mode: 'strip'});
  return import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'));
}
const parser = await load('dxfParser');
// These two imports are type-only; the production source omits `import type`.
const scene = await load('scene3d', s => s.replace("import { ParsedDxfModel, DxfEntity } from './dxfParser.js';", ''));
const changes = await load('changeset', s => s
  .replace("import { DrawingsManager } from './drawings.js';", '')
  .replace("import { StandardsManager } from './standards.js';", ''));
const sample = fs.readFileSync(path.join(root, 'Draff/fixtures/synthetic/hygiene_ok.dxf'), 'utf8');
const invalid = parser.parseDxfContent('THIS IS NOT A DXF', 'invalid.dxf');
const invalidResult = parser.renderDxfToSheetsAndFindings(invalid);
// Direct synthetic entities isolate the branch that suppresses the units check.
const zModel = parser.parseDxfContent(sample, 'z-and-units.dxf');
zModel.insunits = 1;
zModel.entities = [{type:'LINE',handle:'P1',layer:'FN-PART-OUTL',space:'Model',pts:[[0,0],[100,0]],zValues:[18],closed:false}];
const zRules = parser.renderDxfToSheetsAndFindings(zModel).findings.map(f => f.rule);
const workspace = path.join(dir, 'node-probe-output');
fs.mkdirSync(workspace, {recursive:true});
const manager = new changes.ChangesetManager(workspace, {}, {});
const proposed = manager.proposeChangeset('synthetic.dxf', 'furniture-v0', [{op:'unsupported_operation'}]);
const applied = manager.applyChangeset(proposed.changeset_id, true);
const outputText = fs.readFileSync(path.join(workspace, applied.output.path), 'utf8');
fs.unlinkSync(path.join(workspace, applied.output.path));
const glbScene = scene.buildSceneFromDxf(zModel);
const result = {
  method: 'Isolated module execution with Node built-in TS stripping; type-only imports removed. Not a production build or browser QA.',
  invalid_input: {units:invalid.insunits,entities:invalid.entities.length,findings:invalidResult.findings.length,sheets:invalidResult.sheets.length},
  simultaneous_z_and_wrong_units: {rules:zRules,units_check_missing:!zRules.includes('DH-09')},
  unsupported_changeset_without_source: {preview_ok:proposed.ok,validation_ok:applied.validation.ok,output_bytes:Buffer.byteLength(outputText),output_text:outputText},
  original_synthetic_entity_count:zModel.entities.length,
  scene_schema:glbScene.schema
};
console.log(JSON.stringify(result,null,2));
