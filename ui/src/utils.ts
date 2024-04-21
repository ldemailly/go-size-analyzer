import {Result} from "./schema/schema.ts";
import {parseResult} from "./generated/schema.ts";

export function loadData(): Result {
    const doc = document.querySelector("#data")!;
    return parseResult(doc.textContent!);
}


export function formatBytes(bytes: number) {
    if (bytes == 0) return '0 B';
    const k = 1024,
        dm = 2,
        sizes = ['B', 'KB', 'MB', 'GB'],
        i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

export function title(s: string): string {
    return s[0].toUpperCase() + s.slice(1);
}
