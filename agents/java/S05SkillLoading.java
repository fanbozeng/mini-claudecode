import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Scanner;
import java.util.TreeMap;
import java.util.concurrent.TimeUnit;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;
import java.util.stream.Stream;

/**
 * 这份代码演示“技能按需加载”。
 *
 * 你可以把它想成一个很聪明的小助手：
 * 1. 它平时只记住“有哪些技能可以学”。
 * 2. 真正需要某个技能时，才去把完整内容拿出来。
 *
 * 这样做的好处是：
 * 1. 平时更省地方。
 * 2. 需要时再加载，比较灵活。
 */
public final class S05SkillLoading {
    // 最多返回多少个字符，防止一次输出太长把屏幕塞满。
    private static final int MAX_OUTPUT_CHARS = 50_000;

    // 这个正则表达式用来拆开 SKILL.md 里的两部分：
    // 前面的 --- 元信息 ---
    // 后面的正文 body
    private static final Pattern FRONTMATTER = Pattern.compile("^---\\R(.*?)\\R---\\R?(.*)$", Pattern.DOTALL);

    // 这个正则表达式用来找环境变量，比如 $HOME 或 ${HOME}
    private static final Pattern ENV_PATTERN = Pattern.compile("\\$\\{([A-Za-z_][A-Za-z0-9_]*)\\}|\\$([A-Za-z_][A-Za-z0-9_]*)");

    // 这些命令太危险，所以我们直接禁止。
    private static final List<String> DANGEROUS_SNIPPETS = List.of(
            "rm -rf /",
            "sudo",
            "shutdown",
            "reboot",
            "> /dev/"
    );

    private S05SkillLoading() {
    }

    public static void main(String[] args) {
        // workdir = 当前工作目录，也就是程序现在站在哪个文件夹里。
        Path workdir = Path.of("").toAbsolutePath().normalize();

        // skillsDir = 放技能文件的目录。
        Path skillsDir = workdir.resolve("skills");

        // configPath = MCP 配置文件的位置。
        Path configPath = workdir.resolve(System.getenv().getOrDefault("MCP_CONFIG_PATH", "mcp_servers.json"));

        // 先准备两个“帮手”：
        // 1. SkillLoader 负责读技能
        // 2. McpRuntime 负责读 MCP 配置
        SkillLoader skillLoader = new SkillLoader(skillsDir);
        McpRuntime mcp = new McpRuntime(workdir, configPath);

        // 先把系统提示词打印出来，方便我们看到程序启动后的“自我介绍”。
        System.out.println(buildSystemPrompt(workdir, skillLoader, mcp));
        System.out.println();
        System.out.println("Commands:");
        System.out.println("  skills");
        System.out.println("  prompt");
        System.out.println("  load <skill-name>");
        System.out.println("  read <path> [limit]");
        System.out.println("  write <path> | <content>");
        System.out.println("  edit <path> | <old-text> | <new-text>");
        System.out.println("  bash <command>");
        System.out.println("  q / exit");
        System.out.println();

        // Scanner 就像“读键盘输入的小助手”。
        try (Scanner scanner = new Scanner(System.in, StandardCharsets.UTF_8)) {
            while (true) {
                System.out.print("s05-java >> ");
                if (!scanner.hasNextLine()) {
                    break;
                }

                // trim() 会把前后空格去掉，避免用户不小心多敲了空格。
                String line = scanner.nextLine().trim();
                if (line.isEmpty() || line.equalsIgnoreCase("q") || line.equalsIgnoreCase("exit")) {
                    break;
                }

                // handleCommand 负责“看懂用户命令，并给出结果”。
                String output = handleCommand(line, workdir, skillLoader, mcp);
                System.out.println(output);
                System.out.println();
            }
        }
    }

    /**
     * 构建系统提示词。
     *
     * 你可以把它理解成给 AI 的“开场白”：
     * 告诉它自己是谁、有哪些技能、有哪些 MCP 服务器。
     */
    public static String buildSystemPrompt(Path workdir, SkillLoader skillLoader, McpRuntime mcp) {
        return "You are a coding agent at " + workdir + ".\n"
                + "Use load_skill to access specialized knowledge before tackling unfamiliar topics.\n"
                + "Use MCP tools when an external integration is a better fit than local shell/file access.\n\n"
                + "Skills available:\n"
                + skillLoader.getDescriptions()
                + "\n\nMCP servers:\n"
                + mcp.describeServers()
                + "\n\nMCP tools:\n"
                + mcp.describeTools();
    }

    /**
     * 确保路径没有逃出工作目录。
     *
     * 为什么要检查？
     * 因为如果用户传入 ../ 这样的路径，就可能跑到项目外面去，
     * 这不安全。
     */
    public static Path safePath(Path workdir, String relativePath) {
        Path root = workdir.toAbsolutePath().normalize();
        Path candidate = root.resolve(relativePath).normalize();
        if (!candidate.startsWith(root)) {
            throw new IllegalArgumentException("Path escapes workspace: " + relativePath);
        }
        return candidate;
    }

    /**
     * 执行一条 shell 命令。
     *
     * 注意：这里只是教学版本，所以做了最基础的危险词检查，
     * 不是完整的安全沙箱。
     */
    public static String runBash(String command, Path workdir) {
        for (String snippet : DANGEROUS_SNIPPETS) {
            if (command.contains(snippet)) {
                return "Error: Dangerous command blocked";
            }
        }

        Process process = null;
        try {
            // /bin/sh -lc command 表示“开一个 shell 来执行这条命令”。
            process = new ProcessBuilder("/bin/sh", "-lc", command)
                    .directory(workdir.toFile())
                    .redirectErrorStream(true)
                    .start();

            // 最多等 120 秒，超时就停止。
            if (!process.waitFor(120, TimeUnit.SECONDS)) {
                process.destroyForcibly();
                return "Error: Timeout (120s)";
            }

            // 读取命令输出，如果空白就告诉用户“没有输出”。
            String output = readFully(process.getInputStream()).trim();
            return output.isEmpty() ? "(no output)" : truncate(output);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            return "Error: " + e.getMessage();
        } catch (IOException e) {
            return "Error: " + e.getMessage();
        } finally {
            if (process != null) {
                process.destroyForcibly();
            }
        }
    }

    /**
     * 读取文件内容。
     *
     * limit 的意思是“最多显示多少行”。
     * 如果文件很长，就只看前面一部分。
     */
    public static String runRead(Path workdir, String path, Integer limit) {
        try {
            List<String> lines = Files.readAllLines(safePath(workdir, path), StandardCharsets.UTF_8);
            if (limit != null && limit < lines.size()) {
                List<String> limited = new ArrayList<>(lines.subList(0, limit));
                limited.add("... (" + (lines.size() - limit) + " more)");
                lines = limited;
            }
            return truncate(String.join("\n", lines));
        } catch (Exception e) {
            return "Error: " + e.getMessage();
        }
    }

    /**
     * 写入文件。
     *
     * 如果父文件夹不存在，就先创建。
     */
    public static String runWrite(Path workdir, String path, String content) {
        try {
            Path target = safePath(workdir, path);
            Path parent = target.getParent();
            if (parent != null) {
                Files.createDirectories(parent);
            }
            Files.writeString(target, content, StandardCharsets.UTF_8);
            return "Wrote " + content.getBytes(StandardCharsets.UTF_8).length + " bytes";
        } catch (Exception e) {
            return "Error: " + e.getMessage();
        }
    }

    /**
     * 编辑文件：把 oldText 替换成 newText。
     *
     * 这里只替换第一次出现的 oldText，
     * 这样行为和原来的 Python 教学版本更接近。
     */
    public static String runEdit(Path workdir, String path, String oldText, String newText) {
        try {
            Path target = safePath(workdir, path);
            String content = Files.readString(target, StandardCharsets.UTF_8);
            if (!content.contains(oldText)) {
                return "Error: Text not found in " + path;
            }
            String updated = content.replaceFirst(Pattern.quote(oldText), Matcher.quoteReplacement(newText));
            Files.writeString(target, updated, StandardCharsets.UTF_8);
            return "Edited " + path;
        } catch (Exception e) {
            return "Error: " + e.getMessage();
        }
    }

    /**
     * 命令分发中心。
     *
     * 它的工作像“前台老师”：
     * 先听你说了什么命令，再决定应该交给谁去处理。
     */
    private static String handleCommand(String line, Path workdir, SkillLoader skillLoader, McpRuntime mcp) {
        if (line.equals("skills")) {
            return skillLoader.getDescriptions();
        }
        if (line.equals("prompt")) {
            return buildSystemPrompt(workdir, skillLoader, mcp);
        }
        if (line.startsWith("load ")) {
            return skillLoader.getContent(line.substring("load ".length()).trim());
        }
        if (line.startsWith("read ")) {
            String[] parts = line.split("\\s+");
            if (parts.length == 2) {
                return runRead(workdir, parts[1], null);
            }
            if (parts.length == 3) {
                try {
                    return runRead(workdir, parts[1], Integer.parseInt(parts[2]));
                } catch (NumberFormatException e) {
                    return "Error: limit must be an integer";
                }
            }
            return "Usage: read <path> [limit]";
        }
        if (line.startsWith("write ")) {
            String[] parts = line.substring("write ".length()).split("\\|", 2);
            if (parts.length != 2) {
                return "Usage: write <path> | <content>";
            }
            return runWrite(workdir, parts[0].trim(), parts[1].trim());
        }
        if (line.startsWith("edit ")) {
            String[] parts = line.substring("edit ".length()).split("\\|", 3);
            if (parts.length != 3) {
                return "Usage: edit <path> | <old-text> | <new-text>";
            }
            return runEdit(workdir, parts[0].trim(), parts[1].trim(), parts[2].trim());
        }
        if (line.startsWith("bash ")) {
            return runBash(line.substring("bash ".length()), workdir);
        }
        return "Unknown command. Try: skills, prompt, load, read, write, edit, bash, exit";
    }

    // 把输入流里的所有内容一次性读出来，变成字符串。
    private static String readFully(InputStream inputStream) throws IOException {
        try (inputStream; ByteArrayOutputStream output = new ByteArrayOutputStream()) {
            inputStream.transferTo(output);
            return output.toString(StandardCharsets.UTF_8);
        }
    }

    // 如果字符串太长，就只保留前面 MAX_OUTPUT_CHARS 个字符。
    private static String truncate(String value) {
        if (value.length() <= MAX_OUTPUT_CHARS) {
            return value;
        }
        return value.substring(0, MAX_OUTPUT_CHARS);
    }

    /**
     * SkillLoader 负责扫描 skills 目录，把所有技能装进内存。
     *
     * 你可以把它当成“图书管理员”：
     * 1. 先登记每本书叫什么名字
     * 2. 记住简介
     * 3. 真要看哪本书时，再把内容拿出来
     */
    public static final class SkillLoader {
        private final Path skillsDir;

        // 用 TreeMap 是为了让技能名字按顺序排好，输出更稳定。
        private final Map<String, SkillEntry> skills = new TreeMap<>();

        public SkillLoader(Path skillsDir) {
            this.skillsDir = skillsDir;
            loadAll();
        }

        /**
         * 返回“技能列表的简短介绍”。
         *
         * 这就是第一层加载：
         * 只告诉你有什么技能，不把完整内容都塞出来。
         */
        public String getDescriptions() {
            if (skills.isEmpty()) {
                return "(no skills available)";
            }

            List<String> lines = new ArrayList<>();
            for (Map.Entry<String, SkillEntry> entry : skills.entrySet()) {
                String description = normalizeDescription(entry.getValue().meta().getOrDefault("description", "No description"));
                String tags = entry.getValue().meta().getOrDefault("tags", "");
                String line = "  - " + entry.getKey() + ": " + description;
                if (!tags.isBlank()) {
                    line += " [" + tags + "]";
                }
                lines.add(line);
            }
            return String.join("\n", lines);
        }

        /**
         * 返回某个技能的完整内容。
         *
         * 这就是第二层加载：
         * 真的需要时，再把技能正文拿出来。
         */
        public String getContent(String name) {
            SkillEntry skill = skills.get(name);
            if (skill == null) {
                String available = String.join(", ", skills.keySet());
                return "Error: Unknown skill '" + name + "'. Available: " + available;
            }
            return "<skill name=\"" + name + "\">\n" + skill.body() + "\n</skill>";
        }

        public Map<String, SkillEntry> getSkills() {
            return Collections.unmodifiableMap(skills);
        }

        // 扫描 skills 目录下所有名叫 SKILL.md 的文件。
        private void loadAll() {
            if (!Files.exists(skillsDir)) {
                return;
            }

            try (Stream<Path> paths = Files.walk(skillsDir)) {
                List<Path> skillFiles = paths
                        .filter(path -> path.getFileName().toString().equals("SKILL.md"))
                        .sorted()
                        .collect(Collectors.toList());

                for (Path skillFile : skillFiles) {
                    String text = Files.readString(skillFile, StandardCharsets.UTF_8);
                    Frontmatter parsed = parseFrontmatter(text);
                    String name = parsed.meta().getOrDefault("name", skillFile.getParent().getFileName().toString());
                    skills.put(name, new SkillEntry(parsed.meta(), parsed.body(), skillFile));
                }
            } catch (IOException e) {
                throw new IllegalStateException("Failed to load skills from " + skillsDir + ": " + e.getMessage(), e);
            }
        }

        // 拆 frontmatter。匹配成功就得到 meta + body；失败就把整个文件当正文。
        private Frontmatter parseFrontmatter(String text) {
            Matcher matcher = FRONTMATTER.matcher(text);
            if (!matcher.matches()) {
                return new Frontmatter(Map.of(), text);
            }

            Map<String, String> meta = parseMetadataBlock(matcher.group(1));
            return new Frontmatter(meta, matcher.group(2).strip());
        }

        /**
         * 解析前面 --- --- 中的键值对。
         *
         * 这里不仅支持：
         * description: hello
         *
         * 还支持：
         * description: |
         *   第一行
         *   第二行
         */
        private Map<String, String> parseMetadataBlock(String raw) {
            List<String> lines = List.of(raw.split("\\R", -1));
            Map<String, String> meta = new LinkedHashMap<>();

            for (int index = 0; index < lines.size(); ) {
                String line = lines.get(index);
                if (line.isBlank()) {
                    index++;
                    continue;
                }

                int separator = line.indexOf(':');
                if (separator < 0) {
                    index++;
                    continue;
                }

                String key = line.substring(0, separator).trim();
                String value = line.substring(separator + 1).trim();

                if (value.equals("|") || value.equals(">")) {
                    // | 和 > 都表示“后面还有多行内容”。
                    // | 倾向保留换行，> 倾向把换行折叠成空格。
                    boolean folded = value.equals(">");
                    List<String> blockLines = new ArrayList<>();
                    int cursor = index + 1;
                    while (cursor < lines.size()) {
                        String candidate = lines.get(cursor);
                        if (!candidate.isBlank() && !Character.isWhitespace(candidate.charAt(0))) {
                            break;
                        }
                        blockLines.add(candidate);
                        cursor++;
                    }
                    value = parseBlockScalar(blockLines, folded);
                    index = cursor;
                } else {
                    index++;
                }

                meta.put(key, value);
            }

            return meta;
        }

        // 处理 YAML 多行文本。
        private String parseBlockScalar(List<String> blockLines, boolean folded) {
            if (blockLines.isEmpty()) {
                return "";
            }

            // 先找最小缩进，等会儿统一去掉。
            int minIndent = Integer.MAX_VALUE;
            for (String line : blockLines) {
                if (line.isBlank()) {
                    continue;
                }
                minIndent = Math.min(minIndent, leadingWhitespace(line));
            }
            if (minIndent == Integer.MAX_VALUE) {
                minIndent = 0;
            }

            List<String> normalized = new ArrayList<>();
            for (String line : blockLines) {
                if (line.isBlank()) {
                    normalized.add("");
                    continue;
                }
                int start = Math.min(minIndent, line.length());
                normalized.add(line.substring(start));
            }

            return folded ? String.join(" ", normalized).trim() : String.join("\n", normalized).trim();
        }

        // 计算一行开头有多少个空白字符。
        private int leadingWhitespace(String line) {
            int count = 0;
            while (count < line.length() && Character.isWhitespace(line.charAt(count))) {
                count++;
            }
            return count;
        }

        // 把多余空白压缩一下，让 description 更适合放在一行里展示。
        private String normalizeDescription(String description) {
            return description
                    .replaceAll("\\s*\\R\\s*", " ")
                    .replaceAll("\\s{2,}", " ")
                    .trim();
        }
    }

    /**
     * McpRuntime 目前是“最小教学版”。
     *
     * 它现在主要做两件事：
     * 1. 读取 MCP 配置文件
     * 2. 把配置概况展示出来
     *
     * 真正去连接远程 MCP 工具，这里还没有实现。
     */
    public static final class McpRuntime {
        private final Path workdir;
        private final Path configPath;
        private final List<McpServerConfig> servers;
        private String configError;

        public McpRuntime(Path workdir, Path configPath) {
            this.workdir = workdir;
            this.configPath = configPath;
            this.servers = loadConfig();
        }

        // 把“有哪些 MCP 服务器”整理成可读文本。
        public String describeServers() {
            if (configError != null) {
                return "(invalid MCP config: " + configError + ")";
            }
            if (!Files.exists(configPath)) {
                return "(no MCP config at " + configPath.getFileName() + ")";
            }
            if (servers.isEmpty()) {
                return "(no MCP servers configured)";
            }
            return servers.stream()
                    .map(server -> "  - " + server.name() + ": " + joinCommand(server.command(), server.args()))
                    .collect(Collectors.joining("\n"));
        }

        // 这里先返回提示语，告诉读代码的人：工具发现功能还没接上。
        public String describeTools() {
            if (configError != null) {
                return "(no MCP tools loaded)";
            }
            if (servers.isEmpty()) {
                return "(no MCP tools loaded)";
            }
            return "(MCP tool discovery requires a dedicated Java MCP client)";
        }

        public boolean hasTool(String name) {
            return false;
        }

        public String callTool(String name, Map<String, Object> arguments) {
            return "Unknown MCP tool: " + name;
        }

        // 读取 mcp_servers.json，并把里面的服务器信息转成 Java 对象。
        private List<McpServerConfig> loadConfig() {
            if (!Files.exists(configPath)) {
                return List.of();
            }

            try {
                // 这里用了下面自己写的 JsonParser，目的是不额外依赖第三方库。
                Object parsed = new JsonParser(Files.readString(configPath, StandardCharsets.UTF_8)).parse();
                if (!(parsed instanceof Map<?, ?> root)) {
                    throw new IllegalArgumentException("root JSON value must be an object");
                }

                Object rawServers = root.get("servers");
                if (!(rawServers instanceof List<?> rawList)) {
                    return List.of();
                }

                List<McpServerConfig> loaded = new ArrayList<>();
                for (Object item : rawList) {
                    if (!(item instanceof Map<?, ?> server)) {
                        continue;
                    }
                    String name = asString(server.get("name"));
                    String command = expand(asString(server.get("command")));
                    List<String> args = asStringList(server.get("args")).stream()
                            .map(this::expand)
                            .collect(Collectors.toList());
                    Map<String, String> env = new LinkedHashMap<>();
                    for (Map.Entry<String, Object> entry : asObjectMap(server.get("env")).entrySet()) {
                        env.put(entry.getKey(), expand(asString(entry.getValue())));
                    }
                    if (!name.isBlank() && !command.isBlank()) {
                        loaded.add(new McpServerConfig(name, command, args, env));
                    }
                }
                return loaded;
            } catch (Exception e) {
                configError = e.getMessage();
                return List.of();
            }
        }

        /**
         * 展开环境变量。
         *
         * 例子：
         * ${HOME}/demo
         * 会被替换成真实的 HOME 路径。
         */
        private String expand(String value) {
            Matcher matcher = ENV_PATTERN.matcher(value);
            StringBuffer buffer = new StringBuffer();
            while (matcher.find()) {
                String key = matcher.group(1) != null ? matcher.group(1) : matcher.group(2);
                String replacement = System.getenv(key);
                if (replacement == null) {
                    replacement = matcher.group();
                }
                matcher.appendReplacement(buffer, Matcher.quoteReplacement(replacement));
            }
            matcher.appendTail(buffer);

            String expanded = buffer.toString();
            if (expanded.startsWith("./") || expanded.startsWith("../")) {
                return workdir.resolve(expanded).normalize().toString();
            }
            return expanded;
        }

        // 把命令和参数拼成一行，方便展示。
        private String joinCommand(String command, List<String> args) {
            if (args.isEmpty()) {
                return command;
            }
            return command + " " + String.join(" ", args);
        }
    }

    private record SkillEntry(Map<String, String> meta, String body, Path path) {
    }

    private record Frontmatter(Map<String, String> meta, String body) {
    }

    private record McpServerConfig(String name, String command, List<String> args, Map<String, String> env) {
    }

    private static String asString(Object value) {
        return value == null ? "" : String.valueOf(value);
    }

    private static List<String> asStringList(Object value) {
        if (!(value instanceof List<?> list)) {
            return List.of();
        }
        List<String> result = new ArrayList<>();
        for (Object item : list) {
            result.add(asString(item));
        }
        return result;
    }

    private static Map<String, Object> asObjectMap(Object value) {
        if (!(value instanceof Map<?, ?> map)) {
            return Map.of();
        }
        Map<String, Object> result = new LinkedHashMap<>();
        for (Map.Entry<?, ?> entry : map.entrySet()) {
            result.put(String.valueOf(entry.getKey()), entry.getValue());
        }
        return result;
    }

    /**
     * 一个很小的 JSON 解析器。
     *
     * 为什么自己写？
     * 因为这个示例想保持“零依赖”，
     * 让你只用 javac 和 java 就能跑起来。
     *
     * 你可以把它理解成：
     * 一个字符一个字符地读，
     * 看到 { 就知道是对象，
     * 看到 [ 就知道是数组，
     * 看到 " 就知道是字符串。
     */
    private static final class JsonParser {
        private final String input;
        private int index;

        private JsonParser(String input) {
            this.input = input;
        }

        // parse() 是总入口。
        private Object parse() {
            skipWhitespace();
            Object value = parseValue();
            skipWhitespace();
            if (index != input.length()) {
                throw error("Unexpected trailing content");
            }
            return value;
        }

        // 根据当前位置的字符，判断接下来是什么类型的数据。
        private Object parseValue() {
            skipWhitespace();
            if (index >= input.length()) {
                throw error("Unexpected end of JSON");
            }

            char current = input.charAt(index);
            return switch (current) {
                case '{' -> parseObject();
                case '[' -> parseArray();
                case '"' -> parseString();
                case 't' -> parseLiteral("true", Boolean.TRUE);
                case 'f' -> parseLiteral("false", Boolean.FALSE);
                case 'n' -> parseLiteral("null", null);
                default -> {
                    if (current == '-' || Character.isDigit(current)) {
                        yield parseNumber();
                    }
                    throw error("Unexpected character '" + current + "'");
                }
            };
        }

        // 解析对象：长得像 {"name": "demo"}
        private Map<String, Object> parseObject() {
            expect('{');
            skipWhitespace();

            Map<String, Object> result = new LinkedHashMap<>();
            if (consume('}')) {
                return result;
            }

            while (true) {
                skipWhitespace();
                String key = parseString();
                skipWhitespace();
                expect(':');
                Object value = parseValue();
                result.put(key, value);
                skipWhitespace();
                if (consume('}')) {
                    return result;
                }
                expect(',');
            }
        }

        // 解析数组：长得像 [1, 2, 3]
        private List<Object> parseArray() {
            expect('[');
            skipWhitespace();

            List<Object> result = new ArrayList<>();
            if (consume(']')) {
                return result;
            }

            while (true) {
                result.add(parseValue());
                skipWhitespace();
                if (consume(']')) {
                    return result;
                }
                expect(',');
            }
        }

        // 解析字符串：长得像 "hello"
        private String parseString() {
            expect('"');
            StringBuilder builder = new StringBuilder();

            while (index < input.length()) {
                char current = input.charAt(index++);
                if (current == '"') {
                    return builder.toString();
                }
                if (current != '\\') {
                    builder.append(current);
                    continue;
                }
                if (index >= input.length()) {
                    throw error("Invalid escape sequence");
                }

                char escaped = input.charAt(index++);
                switch (escaped) {
                    case '"', '\\', '/' -> builder.append(escaped);
                    case 'b' -> builder.append('\b');
                    case 'f' -> builder.append('\f');
                    case 'n' -> builder.append('\n');
                    case 'r' -> builder.append('\r');
                    case 't' -> builder.append('\t');
                    case 'u' -> builder.append(parseUnicodeEscape());
                    default -> throw error("Invalid escape character '" + escaped + "'");
                }
            }

            throw error("Unterminated string");
        }

        // 解析 \u4F60 这样的 unicode 转义。
        private char parseUnicodeEscape() {
            if (index + 4 > input.length()) {
                throw error("Incomplete unicode escape");
            }
            String hex = input.substring(index, index + 4);
            index += 4;
            return (char) Integer.parseInt(hex, 16);
        }

        // 解析 true / false / null 这些固定单词。
        private Object parseLiteral(String literal, Object value) {
            if (!input.startsWith(literal, index)) {
                throw error("Expected '" + literal + "'");
            }
            index += literal.length();
            return value;
        }

        // 解析数字，比如 123、-5、3.14。
        private Number parseNumber() {
            int start = index;
            if (peek('-')) {
                index++;
            }
            consumeDigits();
            if (peek('.')) {
                index++;
                consumeDigits();
            }
            if (peek('e') || peek('E')) {
                index++;
                if (peek('+') || peek('-')) {
                    index++;
                }
                consumeDigits();
            }

            String token = input.substring(start, index);
            if (token.contains(".") || token.contains("e") || token.contains("E")) {
                return Double.parseDouble(token);
            }
            return Long.parseLong(token);
        }

        // 连续吃掉一串数字。
        private void consumeDigits() {
            if (index >= input.length() || !Character.isDigit(input.charAt(index))) {
                throw error("Expected digit");
            }
            while (index < input.length() && Character.isDigit(input.charAt(index))) {
                index++;
            }
        }

        // 跳过空格、换行、Tab 这些空白字符。
        private void skipWhitespace() {
            while (index < input.length() && Character.isWhitespace(input.charAt(index))) {
                index++;
            }
        }

        // 必须读到某个字符，否则报错。
        private void expect(char expected) {
            if (index >= input.length() || input.charAt(index) != expected) {
                throw error("Expected '" + expected + "'");
            }
            index++;
        }

        // 如果当前位置正好是 expected，就消费掉它并返回 true。
        private boolean consume(char expected) {
            if (peek(expected)) {
                index++;
                return true;
            }
            return false;
        }

        // 只是看看当前位置是不是 expected，但不移动 index。
        private boolean peek(char expected) {
            return index < input.length() && input.charAt(index) == expected;
        }

        // 统一生成带位置的错误信息，方便调试。
        private IllegalArgumentException error(String message) {
            return new IllegalArgumentException(message + " at index " + index);
        }
    }
}
