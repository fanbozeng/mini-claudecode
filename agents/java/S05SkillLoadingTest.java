import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * 这不是给机器看的“高深测试”。
 * 你可以把它当成“自动检查作业的老师”。
 *
 * 它会一件一件检查：
 * 1. 技能有没有读对
 * 2. 读写文件有没有工作
 * 3. MCP 配置有没有显示出来
 */
public final class S05SkillLoadingTest {
    private S05SkillLoadingTest() {
    }

    public static void main(String[] args) throws Exception {
        // 创建一个临时文件夹，这样测试时不会乱改真实项目文件。
        Path tempDir = Files.createTempDirectory("s05-skill-loading-java");
        try {
            testSkillLoaderParsesFrontmatter(tempDir);
            testFileToolsStayInsideWorkspace(tempDir);
            testMcpConfigAppearsInSystemPrompt(tempDir);
            System.out.println("S05SkillLoadingTest passed");
        } finally {
            deleteRecursively(tempDir);
        }
    }

    // 这组测试检查：技能文件能不能被正确解析。
    private static void testSkillLoaderParsesFrontmatter(Path tempDir) throws IOException {
        Path skillsDir = tempDir.resolve("skills");
        Files.createDirectories(skillsDir.resolve("pdf"));
        Files.createDirectories(skillsDir.resolve("code-review"));

        // 准备一个最普通的技能文件。
        Files.writeString(
                skillsDir.resolve("pdf/SKILL.md"),
                """
                ---
                name: pdf
                description: Process PDF files
                tags: docs,files
                ---
                Step 1: open the PDF
                Step 2: extract the text
                """
        );

        // 这个技能没有写 name，所以程序应该退回去用文件夹名字 code-review。
        Files.writeString(
                skillsDir.resolve("code-review/SKILL.md"),
                """
                ---
                description: Review code carefully
                ---
                Check for correctness first
                """
        );

        // 这个技能用的是 YAML 多行写法。
        // 我们想确认 Java 版解析器能看懂它。
        Files.createDirectories(skillsDir.resolve("agent-builder"));
        Files.writeString(
                skillsDir.resolve("agent-builder/SKILL.md"),
                """
                ---
                description: |
                  Design and build AI agents
                  with multi-step workflows
                ---
                Build small agent loops first
                """
        );

        S05SkillLoading.SkillLoader loader = new S05SkillLoading.SkillLoader(skillsDir);
        String descriptions = loader.getDescriptions();

        // 下面这些断言就是“老师批改作业”：
        // 如果条件不成立，就说明程序和我们预期的不一样。
        assertContains(descriptions, "  - pdf: Process PDF files [docs,files]");
        assertContains(descriptions, "  - code-review: Review code carefully");
        assertContains(descriptions, "  - agent-builder: Design and build AI agents with multi-step workflows");
        assertContains(loader.getContent("pdf"), "<skill name=\"pdf\">");
        assertContains(loader.getContent("pdf"), "Step 2: extract the text");
        assertContains(loader.getContent("missing"), "Error: Unknown skill 'missing'.");
    }

    // 这组测试检查：读文件、写文件、改文件、安全路径这些工具能不能工作。
    private static void testFileToolsStayInsideWorkspace(Path tempDir) throws IOException {
        String writeResult = S05SkillLoading.runWrite(tempDir, "notes/demo.txt", "hello\nhello");
        assertContains(writeResult, "Wrote ");

        String edited = S05SkillLoading.runEdit(tempDir, "notes/demo.txt", "hello", "hi");
        assertEquals("Edited notes/demo.txt", edited);
        assertEquals("hi\nhello", S05SkillLoading.runRead(tempDir, "notes/demo.txt", null));
        assertEquals("hi\n... (1 more)", S05SkillLoading.runRead(tempDir, "notes/demo.txt", 1));
        assertThrows(IllegalArgumentException.class, () -> S05SkillLoading.safePath(tempDir, "../escape.txt"));
        assertEquals("Error: Dangerous command blocked", S05SkillLoading.runBash("sudo echo nope", tempDir));
    }

    // 这组测试检查：MCP 配置读完之后，系统提示词里能不能看到服务器信息。
    private static void testMcpConfigAppearsInSystemPrompt(Path tempDir) throws IOException {
        Path configPath = tempDir.resolve("mcp_servers.json");
        Files.writeString(
                configPath,
                """
                {
                  "servers": [
                    {
                      "name": "demo",
                      "command": "python",
                      "args": ["server.py"],
                      "env": {"MODE": "demo"}
                    }
                  ]
                }
                """
        );

        Path skillsDir = tempDir.resolve("skills");
        Files.createDirectories(skillsDir.resolve("git"));
        Files.writeString(
                skillsDir.resolve("git/SKILL.md"),
                """
                ---
                description: Git workflow helpers
                ---
                Use small commits
                """
        );

        S05SkillLoading.SkillLoader loader = new S05SkillLoading.SkillLoader(skillsDir);
        S05SkillLoading.McpRuntime mcp = new S05SkillLoading.McpRuntime(tempDir, configPath);
        String prompt = S05SkillLoading.buildSystemPrompt(tempDir, loader, mcp);

        assertContains(mcp.describeServers(), "  - demo: python server.py");
        assertContains(prompt, "Skills available:");
        assertContains(prompt, "  - git: Git workflow helpers");
        assertContains(prompt, "MCP servers:");
        assertContains(prompt, "  - demo: python server.py");
    }

    // 断言 actual 里必须包含 expectedFragment。
    private static void assertContains(String actual, String expectedFragment) {
        if (!actual.contains(expectedFragment)) {
            throw new AssertionError("Expected to find '" + expectedFragment + "' in:\n" + actual);
        }
    }

    // 断言两个字符串必须完全一样。
    private static void assertEquals(String expected, String actual) {
        if (!expected.equals(actual)) {
            throw new AssertionError("Expected:\n" + expected + "\nActual:\n" + actual);
        }
    }

    // 断言“这段代码应该抛出某种异常”。
    private static void assertThrows(Class<? extends Throwable> expected, ThrowingRunnable runnable) {
        try {
            runnable.run();
        } catch (Throwable actual) {
            if (expected.isInstance(actual)) {
                return;
            }
            throw new AssertionError("Expected " + expected.getName() + " but got " + actual.getClass().getName(), actual);
        }
        throw new AssertionError("Expected exception " + expected.getName());
    }

    // 测试结束后，把临时目录删干净。
    private static void deleteRecursively(Path path) throws IOException {
        if (!Files.exists(path)) {
            return;
        }
        Files.walk(path)
                .sorted((left, right) -> right.compareTo(left))
                .forEach(current -> {
                    try {
                        Files.deleteIfExists(current);
                    } catch (IOException e) {
                        throw new RuntimeException(e);
                    }
                });
    }

    // 这是一个“可以抛异常的小函数接口”，方便传 lambda 进去测试。
    @FunctionalInterface
    private interface ThrowingRunnable {
        void run() throws Exception;
    }
}
