import React, {
  useState,
  useEffect,
  useCallback,
  useRef,
  useMemo,
} from "react";
import {
  Layout,
  Card,
  Input,
  Select,
  Typography,
  Drawer,
  List,
  Spin,
  message,
  AutoComplete,
  Tabs,
  Tooltip,
  Button,
  Statistic,
  Row,
  Col,
  Divider,
  Badge,
  Space,
} from "antd";
import {
  SearchOutlined,
  AppstoreOutlined,
  BranchesOutlined,
  ExpandOutlined,
  CompressOutlined,
  FileTextOutlined,
  FunctionOutlined,
  NodeIndexOutlined,
  InfoCircleOutlined,
  LinkOutlined,
  CodeOutlined,
  EyeOutlined,
} from "@ant-design/icons";
import ForceGraph3D from "react-force-graph-3d";
import { SketchPicker } from "react-color";
import axios from "axios";
import SyntaxHighlighter from "react-syntax-highlighter";
import { docco } from "react-syntax-highlighter/dist/esm/styles/hljs";

const { Header, Content, Sider } = Layout;
const { Option } = Select;
const { Title, Text } = Typography;
const { TabPane } = Tabs;

const GRAPH_TYPES = {
  REPOS: "repos",
  FULL: "full",
};

const NodeDetailsContent = React.memo(({ details, onClose, onNodeFocus }) => {
  return (
    <Card
      className="node-details-card"
      style={{ borderRadius: 10, padding: 20 }}
    >
      <Space direction="vertical" size="large" style={{ width: "100%" }}>
        <Row gutter={16} align="middle">
          <Col>
            <Badge count={details.type} style={{ backgroundColor: "#52c41a" }}>
              <Title level={4} style={{ margin: 0 }}>
                {details.id.split("/").pop()}
              </Title>
            </Badge>
          </Col>
        </Row>

        <Tabs defaultActiveKey="1">
          <TabPane
            tab={
              <span>
                <FunctionOutlined /> Functions
              </span>
            }
            key="1"
          >
            <List
              dataSource={details.functions || []}
              renderItem={(func, index) => (
                <List.Item key={index}>
                  <Tooltip title="View function code">
                    <Card
                      hoverable
                      onClick={() =>
                        message.info(`Viewing code for ${func.name}`)
                      }
                      style={{ width: "100%", borderRadius: 10 }}
                    >
                      <Card.Meta
                        avatar={<CodeOutlined />}
                        title={func.name}
                        description={
                          <Text ellipsis>{func.body.split("\n")[0]}</Text>
                        }
                      />
                    </Card>
                  </Tooltip>
                </List.Item>
              )}
            />
          </TabPane>
          <TabPane
            tab={
              <span>
                <LinkOutlined /> Imports
              </span>
            }
            key="2"
          >
            <List
              dataSource={details.imports || []}
              renderItem={(item, index) => (
                <List.Item key={index}>
                  <Card style={{ width: "100%", borderRadius: 10 }}>
                    <Text>
                      <FileTextOutlined /> {item}
                    </Text>
                  </Card>
                </List.Item>
              )}
            />
          </TabPane>
          <TabPane
            tab={
              <span>
                <NodeIndexOutlined /> Connected Nodes
              </span>
            }
            key="3"
          >
            <List
              dataSource={details.connectedNodes || []}
              renderItem={(node) => (
                <List.Item key={node.id} onClick={() => onNodeFocus(node)}>
                  <Card hoverable style={{ width: "100%", borderRadius: 10 }}>
                    <Text>
                      <InfoCircleOutlined /> {node.id}
                    </Text>
                  </Card>
                </List.Item>
              )}
            />
          </TabPane>
        </Tabs>
      </Space>
    </Card>
  );
});

const Chat = () => {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");

  const sendMessage = async (message) => {
    setMessages([...messages, { text: message, user: "You" }]);
    setInputValue("");
    try {
      const response = await axios.post("http://localhost:11434/api/generate", {
        prompt: message,
      });
      setMessages((prevMessages) => [
        ...prevMessages,
        { text: response.data.response, user: "LLM" },
      ]);
    } catch (error) {
      console.error("Error sending message:", error);
      message.error("Failed to send message");
    }
  };

  return (
    <div style={{ padding: 20 }}>
      <List
        dataSource={messages}
        renderItem={(msg, index) => (
          <List.Item
            key={index}
            style={{ textAlign: msg.user === "You" ? "right" : "left" }}
          >
            <Card
              style={{
                backgroundColor: msg.user === "You" ? "#f0f0f0" : "#e6f7ff",
                borderRadius: 10,
              }}
            >
              <Typography.Text strong>{msg.user}:</Typography.Text> {msg.text}
            </Card>
          </List.Item>
        )}
      />
      <Input
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onPressEnter={() => sendMessage(inputValue)}
        placeholder="Type a message..."
        style={{ marginTop: 10 }}
      />
      <Button
        type="primary"
        onClick={() => sendMessage(inputValue)}
        style={{ marginTop: 10 }}
        disabled={!inputValue.trim()}
      >
        Send
      </Button>
    </div>
  );
};

const App = () => {
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [graphType, setGraphType] = useState(GRAPH_TYPES.REPOS);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [nodeDetails, setNodeDetails] = useState(null);
  const [graphDimensions, setGraphDimensions] = useState({
    width: 0,
    height: 0,
  });
  const [isFullScreen, setIsFullScreen] = useState(false);
  const [highlightedNodes, setHighlightedNodes] = useState([]);
  const [searchResults, setSearchResults] = useState([]);
  const [fileTrees, setFileTrees] = useState({});
  const [selectionMode, setSelectionMode] = useState(false);
  const [impactStats, setImpactStats] = useState({
    files: 0,
    percentage: 0,
    impactLevel: "",
    nodes: [],
  });
  const [selectedValue, setSelectedValue] = useState("");
  const [highlightColor, setHighlightColor] = useState("#ff7f0e"); // Default highlight color

  const fgRef = useRef();
  const graphContainerRef = useRef();

  const memoizedGraphData = useMemo(() => graphData, [graphData]);

  const fetchGraphData = useCallback(async (type) => {
    setLoading(true);
    try {
      const response = await axios.get(
        `/api/graph-data/${type === GRAPH_TYPES.REPOS ? "repos_graph.json" : "full_graph.json"}`,
      );
      setGraphData(response.data);
      setSearchResults([]);
    } catch (error) {
      console.error("Error fetching graph data:", error);
      message.error("Failed to fetch graph data");
    }
    setLoading(false);
  }, []);

  const fetchFileTrees = useCallback(async () => {
    try {
      const response = await axios.get("/api/tree-node-data/file_trees.json");
      setFileTrees(response.data);
    } catch (error) {
      console.error("Error fetching file trees:", error);
      message.error("Failed to fetch file trees");
    }
  }, []);

  useEffect(() => {
    fetchGraphData(graphType);
    fetchFileTrees();
  }, [fetchGraphData, fetchFileTrees, graphType]);

  useEffect(() => {
    const updateDimensions = () => {
      if (graphContainerRef.current) {
        const { width, height } =
          graphContainerRef.current.getBoundingClientRect();
        setGraphDimensions({ width, height });
      }
    };

    updateDimensions();
    window.addEventListener("resize", updateDimensions);
    return () => window.removeEventListener("resize", updateDimensions);
  }, []);

  const calculateImpact = useCallback(
    (nodes) => {
      const totalNodes = memoizedGraphData.nodes.length;
      const impactedNodes = nodes.length;
      const percentage = ((impactedNodes / totalNodes) * 100).toFixed(2);
      const impactLevel = percentage > 50 ? "CRITICAL" : "MODERATE";

      return {
        files: impactedNodes,
        percentage,
        impactLevel,
        nodes,
      };
    },
    [memoizedGraphData.nodes.length],
  );

  useEffect(() => {
    if (selectionMode) {
      setImpactStats(calculateImpact(highlightedNodes));
    }
  }, [highlightedNodes, selectionMode, calculateImpact]);

  const resetImpactStats = () => {
    setImpactStats({
      files: 0,
      percentage: 0,
      impactLevel: "",
      nodes: [],
    });
  };

  const handleNodeClick = useCallback(
    (node) => {
      const getFullClosure = (startNode, links) => {
        const visited = new Set();
        const queue = [startNode];
        while (queue.length > 0) {
          const currentNode = queue.shift();
          if (!visited.has(currentNode.id)) {
            visited.add(currentNode.id);
            links.forEach((link) => {
              if (link.source.id === currentNode.id) {
                queue.push(link.target);
              } else if (link.target.id === currentNode.id) {
                queue.push(link.source);
              }
            });
          }
        }
        return [...visited].map((id) =>
          memoizedGraphData.nodes.find((n) => n.id === id),
        );
      };

      const fullClosure = getFullClosure(node, memoizedGraphData.links);
      setHighlightedNodes(fullClosure);
      setTimeout(() => {
        focusOnNode(node);
      }, 1200);

      const nodeData = fileTrees[node.id] || { type: "unknown" };
      const connectedNodes = memoizedGraphData.links
        .filter(
          (link) => link.source.id === node.id || link.target.id === node.id,
        )
        .map((link) =>
          link.source.id === node.id ? link.target : link.source,
        );

      if (selectionMode) {
        const newHighlightedNodes = [
          ...new Set([...highlightedNodes, node, ...connectedNodes]),
        ];
        setHighlightedNodes(newHighlightedNodes);
      } else {
        setNodeDetails({ id: node.id, ...nodeData, connectedNodes });
        setDrawerVisible(true);
      }
    },
    [
      fileTrees,
      memoizedGraphData.links,
      selectionMode,
      highlightedNodes,
      calculateImpact,
    ],
  );

  const handleNodeHover = useCallback(
    (node) => {
      if (!selectionMode && node) {
        const relatedNodes = new Set();
        memoizedGraphData.links.forEach((link) => {
          if (link.source.id === node.id) {
            relatedNodes.add(link.target);
          } else if (link.target.id === node.id) {
            relatedNodes.add(link.source);
          }
        });
        setHighlightedNodes([node, ...Array.from(relatedNodes)]);
      } else if (!selectionMode) {
        setHighlightedNodes([]);
      }
    },
    [selectionMode, memoizedGraphData.links],
  );

  const getNodeColor = useCallback(
    (node) => {
      if (highlightedNodes.includes(node)) {
        return highlightColor; // Highlight color for selected nodes
      }
      return "#9c9c9c"; // Default gray color for other nodes
    },
    [highlightedNodes, highlightColor],
  );

  const nodeColor = useCallback((node) => getNodeColor(node), [getNodeColor]);

  const linkColor = useCallback(
    (link) => {
      if (
        highlightedNodes.some(
          (highlightedNode) =>
            link.source === highlightedNode || link.target === highlightedNode,
        )
      ) {
        return highlightColor; // Highlight color for selected links
      }
      return "#8c8c8c40"; // Default gray color for other links
    },
    [highlightedNodes, highlightColor],
  );

  const nodeVal = useCallback(
    (node) => {
      if (highlightedNodes.includes(node)) return 15;
      if (
        highlightedNodes.some((highlightedNode) =>
          memoizedGraphData.links.some(
            (link) =>
              (link.source === highlightedNode && link.target === node) ||
              (link.target === highlightedNode && link.source === node),
          ),
        )
      ) {
        return 6;
      }
      return 3;
    },
    [highlightedNodes, memoizedGraphData.links],
  );

  const linkWidth = useCallback(
    (link) => {
      if (
        highlightedNodes.some(
          (highlightedNode) =>
            link.source === highlightedNode || link.target === highlightedNode,
        )
      ) {
        return 2;
      }
      return 0.3;
    },
    [highlightedNodes],
  );

  const handleSearch = useCallback(
    (value) => {
      const filteredNodes = memoizedGraphData.nodes.filter((node) => {
        const searchField =
          graphType === "repos" ? node.id : node.id.split("/").pop() || node.id;
        return searchField.toLowerCase().includes(value.toLowerCase());
      });
      setSearchResults(
        filteredNodes.map((node) => ({
          value: node.id,
          label: (
            <Space>
              <span
                style={{
                  display: "inline-block",
                  width: 10,
                  height: 10,
                  backgroundColor: getNodeColor(node),
                  borderRadius: "50%",
                }}
              />
              {graphType === "repos"
                ? node.id
                : node.id.split("/").pop() || node.id}
            </Space>
          ),
        })),
      );
    },
    [graphType, memoizedGraphData.nodes, getNodeColor],
  );

  const handleSearchSelect = useCallback(
    (value, option) => {
      setSelectedValue(option.label); // Set the trimmed value to the input field
      const selectedNode = memoizedGraphData.nodes.find(
        (node) => node.id === value,
      );
      if (selectedNode) {
        handleNodeClick(selectedNode);
      }
    },
    [memoizedGraphData.nodes, handleNodeClick],
  );

  const focusOnNode = useCallback((node) => {
    if (fgRef.current) {
      const distance = 240;
      const distRatio = 1 + distance / Math.hypot(node.x, node.y, node.z);
      fgRef.current.cameraPosition(
        { x: node.x * distRatio, y: node.y * distRatio, z: node.z * distRatio }, // new position
        node, // lookAt ({ x, y, z })
        3000, // ms transition duration
      );
    }
  }, []);

  const toggleFullScreen = useCallback(() => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen();
      setIsFullScreen(true);
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
        setIsFullScreen(false);
      }
    }
  }, []);

  const toggleSelectionMode = () => {
    setSelectionMode((prev) => !prev);
    setHighlightedNodes([]);
    resetImpactStats();
  };

  return (
    <Layout style={{ height: "100vh" }}>
      <Header
        style={{
          background: "#001529",
          padding: "0 20px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <Title level={3} style={{ margin: 0, color: "#fff" }}>
          Code Graph Visualization
        </Title>
        <Space>
          <Tooltip title="Toggle Selection Mode">
            <Button
              icon={selectionMode ? <CompressOutlined /> : <ExpandOutlined />}
              onClick={toggleSelectionMode}
            >
              {selectionMode ? "Exit Selection Mode" : "Enter Selection Mode"}
            </Button>
          </Tooltip>
          <Tooltip title="Toggle fullscreen">
            {isFullScreen ? (
              <Button icon={<CompressOutlined />} onClick={toggleFullScreen} />
            ) : (
              <Button icon={<ExpandOutlined />} onClick={toggleFullScreen} />
            )}
          </Tooltip>
        </Space>
      </Header>
      <Layout>
        <Sider width={300} theme="light">
          <Card style={{ height: "100%", borderRadius: 10 }}>
            <Space direction="vertical" style={{ width: "100%" }}>
              <Select
                style={{ width: "100%" }}
                placeholder="Select a graph type"
                onChange={(value) => {
                  setGraphType(value);
                  setSearchResults([]);
                }}
                value={graphType}
              >
                <Option value={GRAPH_TYPES.REPOS}>
                  <AppstoreOutlined /> Repos Graph
                </Option>
                <Option value={GRAPH_TYPES.FULL}>
                  <BranchesOutlined /> Full Graph
                </Option>
              </Select>
              <AutoComplete
                options={searchResults}
                onSelect={handleSearchSelect}
                onSearch={handleSearch}
                value={selectedValue}
                style={{ width: "100%" }}
              >
                <Input
                  placeholder="Search nodes..."
                  prefix={<SearchOutlined />}
                />
              </AutoComplete>
              <Divider />
              <Row gutter={16}>
                <Col span={12}>
                  <Statistic
                    title="Nodes"
                    value={memoizedGraphData.nodes.length}
                  />
                </Col>
                <Col span={12}>
                  <Statistic
                    title="Links"
                    value={memoizedGraphData.links.length}
                  />
                </Col>
              </Row>
              <Divider />
              <Title level={5}>
                Calculated Impact: {impactStats.percentage}% [
                {impactStats.impactLevel}]
              </Title>
              <Text>
                Files: {impactStats.files}/{memoizedGraphData.nodes.length}
              </Text>
              <div
                style={{
                  maxHeight: "200px",
                  overflow: "auto",
                }}
              >
                <List
                  size="small"
                  bordered
                  dataSource={impactStats.nodes.map((node) =>
                    node.id.split("/").pop(),
                  )}
                  renderItem={(item) => (
                    <List.Item
                      style={{
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {item}
                    </List.Item>
                  )}
                />
              </div>
              <Divider />
              <Title level={5}>Highlight Color</Title>
              <SketchPicker
                color={highlightColor}
                onChangeComplete={(color) => setHighlightColor(color.hex)}
              />
            </Space>
          </Card>
        </Sider>
        <Layout style={{ padding: "24px" }}>
          <Content
            ref={graphContainerRef}
            style={{
              background: "#1c1c1c",
              margin: 0,
              minHeight: 280,
              height: "calc(100vh - 64px - 48px)",
              position: "relative",
            }}
          >
            <Tabs defaultActiveKey="1">
              <TabPane tab="Graph" key="1">
                {loading ? (
                  <Spin
                    size="large"
                    style={{
                      position: "absolute",
                      top: "50%",
                      left: "50%",
                      transform: "translate(-50%, -50%)",
                    }}
                  />
                ) : (
                  <ForceGraph3D
                    ref={fgRef}
                    graphData={memoizedGraphData}
                    nodeLabel={(node) => node.id.split("/").pop()}
                    nodeColor={nodeColor}
                    nodeVal={nodeVal}
                    linkWidth={linkWidth}
                    linkColor={linkColor}
                    linkOpacity={0.8}
                    linkDirectionalParticles={1}
                    linkDirectionalParticleWidth={1}
                    linkDirectionalParticleColor={() => "#ffffff"}
                    backgroundColor="#1c1c1c"
                    onNodeClick={handleNodeClick}
                    onNodeHover={handleNodeHover}
                    width={graphDimensions.width}
                    height={graphDimensions.height}
                  />
                )}
              </TabPane>
              <TabPane tab="Chat" key="2">
                <Chat />
              </TabPane>
            </Tabs>
          </Content>
        </Layout>
      </Layout>
      <Drawer
        title="Node Details"
        placement="right"
        closable={true}
        onClose={() => {
          setDrawerVisible(false);
          setHighlightedNodes([]);
        }}
        visible={drawerVisible}
        width={400}
      >
        {nodeDetails && (
          <NodeDetailsContent
            details={nodeDetails}
            onNodeFocus={focusOnNode}
            onClose={() => {
              setDrawerVisible(false);
              setHighlightedNodes([]);
            }}
          />
        )}
      </Drawer>
    </Layout>
  );
};

export default App;
