package agents;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.HashMap;
import java.util.Map;
import java.util.stream.Collectors;
import java.util.stream.Stream;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class S05SkillLoading {
    public static class Skill {
        public final Map<String, String> meta;
        public final String body;
        public final Path path;

        public Skill(Map<String, String> meta, String body, Path path) {
            this.meta = meta;
            this.body = body;
            this.path = path;
        }
    }

    public static class SkillLoader {
        private final Path skillsDir;
        private final Map<String, Skill> skills = new HashMap<>();

        public SkillLoader(Path skillsDir) {
            this.skillsDir = skillsDir;
            loadAll();
        }

        private void loadAll() {
            if (!Files.exists(skillsDir)) {
                return;
            }
            try (Stream<Path> stream = Files.walk(skillsDir)) {
                stream.filter(p -> p.getFileName().toString().equals("SKILL.md"))
                        .sorted()
                        .forEach(path -> {
                            try {
                                String text = Files.readString(path, StandardCharsets.UTF_8);
                                Map.Entry<Map<String, String>, String> parsed = parseFrontmatter(text);
                                Map<String, String> meta = parsed.getKey();
                                String body = parsed.getValue();
                                String name = meta.getOrDefault("name", path.getParent().getFileName().toString());
                                skills.put(name, new Skill(meta, body, path));
                            } catch (IOException e) {
                                System.err.println("Failed to read " + path + ": " + e.getMessage());
                            }
                        });
            } catch (IOException e) {
                throw new RuntimeException("Failed to scan skills directory", e);
            }
        }

        private Map.Entry<Map<String, String>, String> parseFrontmatter(String text) {
            Pattern p = Pattern.compile("(?s)^---\\s*\\n(.*?)\\n---\\s*\\n(.*)$");
            Matcher m = p.matcher(text);
            if (!m.find()) {
                return Map.entry(Map.of(), text.trim());
            }
            Map<String, String> meta = new HashMap<>();
            String front = m.group(1);
            for (String line : front.split("\\r?\\n")) {
                if (!line.contains(":")) continue;
                String[] parts = line.split(":", 2);
                meta.put(parts[0].trim(), parts[1].trim());
            }
            String body = m.group(2).trim();
            return Map.entry(meta, body);
        }

        public String getDescriptions() {
            if (skills.isEmpty()) {
                return "(no skills available)";
            }
            return skills.entrySet().stream()
                    .map(e -> {
                        String desc = e.getValue().meta.getOrDefault("description", "No description");
                        String tags = e.getValue().meta.getOrDefault("tags", "");
                        String line = String.format("  - %s: %s", e.getKey(), desc);
                        if (!tags.isBlank()) {
                            line += String.format(" [%s]", tags);
                        }
                        return line;
                    })
                    .collect(Collectors.joining("\n"));
        }

        public String getContent(String name) {
            Skill skill = skills.get(name);
            if (skill == null) {
                return String.format("Error: Unknown skill '%s'. Available: %s", name,
                        String.join(", ", skills.keySet()));
            }
            return String.format("<skill name=\"%s\">\n%s\n</skill>", name, skill.body);
        }

        public Map<String, Skill> getSkills() {
            return skills;
        }
    }

    public static void main(String[] args) {
        Path workdir = Paths.get(System.getProperty("user.dir"));
        Path skillsDir = workdir.resolve("skills");
        SkillLoader loader = new SkillLoader(skillsDir);

        if (args.length == 0) {
            System.out.println("Usage: java agents.S05SkillLoading list|load <name>");
            return;
        }

        String cmd = args[0];
        if ("list".equalsIgnoreCase(cmd)) {
            System.out.println("Skills available:");
            System.out.println(loader.getDescriptions());
        } else if ("load".equalsIgnoreCase(cmd)) {
            if (args.length < 2) {
                System.err.println("Error: load requires a skill name");
                System.exit(1);
            }
            String name = args[1];
            System.out.println(loader.getContent(name));
        } else {
            System.err.println("Unknown command: " + cmd);
            System.out.println("Usage: java agents.S05SkillLoading list|load <name>");
            System.exit(2);
        }
    }
}
