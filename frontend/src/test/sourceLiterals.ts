import ts from 'typescript';

/**
 * The copy in one source file, for the language lints (Plan 20 §5.8): string and template literal
 * text and JSX text. Import and export paths and `className` values are skipped, so Tailwind
 * classes and the attribute name itself never trip the "class" lint in Plan 19's BANNED_WORDS.
 */
export function sourceLiterals(fileName: string, source: string): string[] {
  const file = ts.createSourceFile(
    fileName,
    source,
    ts.ScriptTarget.Latest,
    true,
    fileName.endsWith('.tsx') ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
  const found: string[] = [];
  const visit = (node: ts.Node): void => {
    if (ts.isImportDeclaration(node) || ts.isExportDeclaration(node)) return;
    if (ts.isJsxAttribute(node) && node.name.getText(file) === 'className') return;
    if (ts.isStringLiteralLike(node) || ts.isJsxText(node)) {
      if (node.text.trim() !== '') found.push(node.text);
    } else if (ts.isTemplateExpression(node)) {
      found.push(node.head.text, ...node.templateSpans.map((span) => span.literal.text));
    }
    ts.forEachChild(node, visit);
  };
  visit(file);
  return found;
}
