import ts from 'typescript';

/**
 * The copy in one source file, for the language lints (Plan 20 §5.8): string and template literal
 * text and JSX text. Import and export paths and `className` values are skipped, so Tailwind
 * classes and the attribute name itself never trip the "class" lint in Plan 19's BANNED_WORDS.
 */
/** `import('./x')` and `vi.mock('./x', ...)`: the path is not copy; the factory still is. */
function isModulePathCall(node: ts.Node): node is ts.CallExpression {
  if (!ts.isCallExpression(node)) return false;
  const callee = node.expression;
  const isImport = callee.kind === ts.SyntaxKind.ImportKeyword;
  const isMock =
    ts.isPropertyAccessExpression(callee) &&
    ts.isIdentifier(callee.expression) &&
    callee.expression.text === 'vi' &&
    callee.name.text === 'mock';
  return isImport || isMock;
}

export function sourceLiterals(fileName: string, source: string): string[] {
  const file = ts.createSourceFile(
    fileName,
    source,
    ts.ScriptTarget.Latest,
    true,
    fileName.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const found: string[] = [];
  const keep = (text: string): void => {
    if (text.trim() !== '') found.push(text);
  };
  const visit = (node: ts.Node): void => {
    if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) return;
    if (ts.isJsxAttribute(node) && node.name.getText(file) === 'className') return;
    if (ts.isPropertyAssignment(node) && node.name.getText(file) === 'className') return;
    if (isModulePathCall(node)) {
      node.arguments.slice(1).forEach(visit);
      return;
    }
    if (ts.isStringLiteralLike(node) || ts.isJsxText(node)) {
      keep(node.text);
    } else if (ts.isTemplateExpression(node)) {
      keep(node.head.text);
      node.templateSpans.forEach((span) => keep(span.literal.text));
    }
    ts.forEachChild(node, visit);
  };
  visit(file);
  return found;
}
