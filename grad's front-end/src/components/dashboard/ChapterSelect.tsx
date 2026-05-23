import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface ChapterSelectProps {
  chapters: string[];
  selectedChapters: string[];
  onSelectionChange: (selected: string[]) => void;
}

const ChapterSelect = ({
  chapters,
  selectedChapters,
  onSelectionChange,
}: ChapterSelectProps) => {
  const allSelected = selectedChapters.length === chapters.length;

  const toggleChapter = (chapter: string) => {
    onSelectionChange(
      selectedChapters.includes(chapter)
        ? selectedChapters.filter((c) => c !== chapter)
        : [...selectedChapters, chapter]
    );
  };

  const toggleAll = () => {
    onSelectionChange(allSelected ? [] : [...chapters]);
  };

  return (
    <div className="space-y-3">
      {/* Select all */}
      <div className="flex items-center gap-2.5">
        <Checkbox
          id="select-all"
          checked={allSelected}
          onCheckedChange={toggleAll}
          className="border-border/60 data-[state=checked]:border-primary data-[state=checked]:bg-primary"
        />
        <Label
          htmlFor="select-all"
          className="cursor-pointer text-xs font-semibold text-foreground"
        >
          Select all chapters
        </Label>
      </div>

      {/* Individual chapters */}
      <div className="ml-0.5 grid gap-2 sm:grid-cols-2">
        {chapters.map((chapter, idx) => {
          const checked = selectedChapters.includes(chapter);
          return (
            <div
              key={idx}
              className={cn(
                "flex items-center gap-2.5 rounded-lg border px-3 py-2 transition-all",
                checked
                  ? "border-primary/30 bg-primary/5"
                  : "border-border/40 bg-transparent hover:border-border/70"
              )}
            >
              <Checkbox
                id={`chapter-${idx}`}
                checked={checked}
                onCheckedChange={() => toggleChapter(chapter)}
                className="border-border/60 data-[state=checked]:border-primary data-[state=checked]:bg-primary"
              />
              <Label
                htmlFor={`chapter-${idx}`}
                className={cn(
                  "cursor-pointer text-xs leading-relaxed",
                  checked ? "text-foreground font-medium" : "text-muted-foreground"
                )}
              >
                {chapter}
              </Label>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default ChapterSelect;
