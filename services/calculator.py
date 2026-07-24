from models import CalcResult, DownloadedFile


class CalculatorService:
    def calculate(self, files: list[DownloadedFile], names: list[str]) -> CalcResult:
        selected = [f for f in files if f.name in names]
        total_counts = {str(d): 0 for d in range(10)}
        file_counts: dict[str, dict[str, int]] = {}

        for f in selected:
            counts = {str(d): 0 for d in range(10)}
            for ch in f.content:
                if ch.isdigit():
                    counts[ch] += 1
                    total_counts[ch] += 1
            file_counts[f.name] = counts

        return CalcResult(total=total_counts, files=file_counts)
