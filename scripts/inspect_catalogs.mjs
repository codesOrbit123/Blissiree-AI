import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const files = process.argv.slice(2);
for (const file of files) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(file));
  const summary = await workbook.inspect({
    kind: "workbook,sheet,table,region",
    maxChars: 14000,
    tableMaxRows: 12,
    tableMaxCols: 16,
    tableMaxCellChars: 180,
  });
  console.log(JSON.stringify({ file, summary: summary.ndjson }));
}
