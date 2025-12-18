"""
知识图谱可视化模块 (最终修复版)
1. 修复 KeyError: 'd' 报错：改用 .replace() 方法注入数据，避免与 JS 模板语法冲突。
2. 保持 D3.js 内置图例和中文适配。
3. 保持 st.components.v1.html 安全渲染。
"""

import json
import networkx as nx
import streamlit as st
import streamlit.components.v1 as components
from typing import Dict, Any, Optional

# --- 节点配色与配置 ---
NODE_CONFIG = {
    "document": {"color": "#6366f1", "radius": 30, "icon": "📄", "label": "Document (文献)"},
    "keyword":  {"color": "#ec4899", "radius": 14, "icon": "🏷️", "label": "Keyword (关键词)"},
    "method":   {"color": "#10b981", "radius": 18, "icon": "⚙️", "label": "Method (方法)"},
    "dataset":  {"color": "#f59e0b", "radius": 16, "icon": "📊", "label": "Dataset (数据集)"},
    "field":    {"color": "#8b5cf6", "radius": 20, "icon": "🎓", "label": "Field (领域)"},
    "application": {"color": "#06b6d4", "radius": 18, "icon": "💻", "label": "Application (应用)"}
}

# --- D3.js 完整模板 ---
# 注意：这里使用标准的 CSS/JS 语法 (单花括号)，因为我们将使用 .replace() 而不是 .format()
D3_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <script src="https://cdn.staticfile.net/d3/7.9.0/d3.min.js"></script>
    <style>
        body { 
            font-family: "Microsoft YaHei", system-ui, sans-serif; 
            background-color: #0f172a; 
            color: #f1f5f9;
            margin: 0; 
            overflow: hidden; 
        }
        
        /* 玻璃拟态面板 */
        .glass {
            background: rgba(30, 41, 59, 0.75);
            backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.5);
            border-radius: 12px;
        }

        /* 侧边栏 */
        #details-panel {
            position: absolute;
            top: 20px; right: 20px; bottom: 20px;
            width: 300px;
            transform: translateX(120%);
            transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            z-index: 20;
            display: flex;
            flex-direction: column;
        }
        #details-panel.open { transform: translateX(0); }

        /* 图例 (Legend) */
        .legend {
            position: absolute;
            bottom: 20px; right: 20px;
            padding: 12px;
            z-index: 10;
            pointer-events: none;
        }
        .legend-item {
            display: flex; align-items: center; gap: 8px;
            margin-bottom: 6px; font-size: 12px; color: #cbd5e1;
        }
        .legend-dot { width: 10px; height: 10px; border-radius: 50%; }

        /* SVG 样式 */
        .node text { 
            pointer-events: none; 
            text-shadow: 0 1px 4px rgba(0,0,0,0.9); 
            font-size: 11px;
            fill: #e2e8f0;
        }
        .link { stroke: #334155; stroke-opacity: 0.4; transition: all 0.3s; }
        .halo { transition: r 0.3s cubic-bezier(0.34, 1.56, 0.64, 1); }
        
        /* 交互高亮类 */
        .dimmed { opacity: 0.1; }
        .highlighted { stroke: #fcd34d; stroke-width: 2px; stroke-opacity: 1; }
        
        /* 滚动条 */
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-thumb { background: #475569; border-radius: 2px; }
    </style>
</head>
<body>
    <!-- 顶部状态栏 -->
    <div style="position:absolute; top:20px; left:20px; z-index:10; display:flex; gap:10px;">
        <div class="glass" style="padding: 6px 12px; font-size: 12px; color: #34d399; display:flex; align-items:center; gap:6px;">
            <span style="width:8px; height:8px; background:#34d399; border-radius:50%; box-shadow: 0 0 8px #34d399;"></span>
            Physics Engine: Active
        </div>
        <div class="glass" style="padding: 6px 12px; font-size: 12px; color: #94a3b8;">
            Nodes: __NODE_COUNT__ | Edges: __EDGE_COUNT__
        </div>
    </div>

    <!-- 右下角图例 -->
    <div class="glass legend">
        <div style="font-weight:bold; margin-bottom:8px; color:#fff; font-size:12px;">Map Legend</div>
        __LEGEND_HTML__
    </div>

    <!-- 左下角缩放控制 -->
    <div id="zoom-controls" class="glass" style="position:absolute; bottom:20px; left:20px; padding:8px; z-index:10; display:flex; flex-direction:column; gap:6px;">
        <button id="zoom-in" class="zoom-btn" title="放大">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/>
            </svg>
        </button>
        <button id="zoom-out" class="zoom-btn" title="缩小">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="8" y1="11" x2="14" y2="11"/>
            </svg>
        </button>
        <button id="zoom-reset" class="zoom-btn" title="复位">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>
            </svg>
        </button>
    </div>
    <style>
        .zoom-btn {
            background: rgba(51, 65, 85, 0.8);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 6px;
            padding: 8px;
            cursor: pointer;
            color: #94a3b8;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .zoom-btn:hover {
            background: rgba(99, 102, 241, 0.3);
            color: #a5b4fc;
            border-color: rgba(99, 102, 241, 0.5);
        }
        .zoom-btn:active {
            transform: scale(0.95);
        }
    </style>

    <!-- 侧边详情栏 -->
    <div id="details-panel" class="glass">
        <div style="padding: 15px; border-bottom: 1px solid rgba(255,255,255,0.1); display:flex; justify-content:space-between;">
            <span id="panel-type" style="font-size:10px; text-transform:uppercase; letter-spacing:1px; color:#94a3b8;">TYPE</span>
            <button onclick="closePanel()" style="background:none; border:none; color:#94a3b8; cursor:pointer;">✕</button>
        </div>
        <div style="padding: 15px; overflow-y:auto; flex:1;">
            <h2 id="panel-title" style="margin:0 0 10px 0; font-size:18px; color:#fff;">Title</h2>
            <div id="panel-content" style="font-size:13px; color:#cbd5e1; line-height:1.6;"></div>
        </div>
    </div>

    <!-- 绘图容器 -->
    <div id="graph"></div>

    <script>
        const data = __GRAPH_DATA__;
        const config = __NODE_CONFIG__;
        const width = window.innerWidth;
        const height = window.innerHeight;

        // 创建 zoom 实例并保存引用
        const zoom = d3.zoom().scaleExtent([0.1, 8]).on("zoom", (e) => g.attr("transform", e.transform));
        
        const svg = d3.select("#graph").append("svg")
            .attr("width", "100%")
            .attr("height", "100%")
            .attr("viewBox", [0, 0, width, height])
            .call(zoom);

        const g = svg.append("g");

        // 力导向模拟
        const simulation = d3.forceSimulation(data.nodes)
            .force("link", d3.forceLink(data.links).id(d => d.id).distance(100))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collide", d3.forceCollide().radius(d => (config[d.group]?.radius || 20) + 5).iterations(2));

        // 连线
        const link = g.append("g")
            .selectAll("line")
            .data(data.links)
            .join("line")
            .attr("class", "link")
            .attr("stroke-width", d => Math.sqrt(d.value || 1));

        // 节点组
        const node = g.append("g")
            .selectAll("g")
            .data(data.nodes)
            .join("g")
            .attr("class", "node")
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended))
            .on("click", (e, d) => showDetails(d));

        // 节点光晕
        node.append("circle")
            .attr("class", "halo")
            .attr("r", d => (config[d.group]?.radius || 10) + 4)
            .attr("fill", d => config[d.group]?.color || "#ccc")
            .attr("opacity", 0.2);

        // 节点实体
        node.append("circle")
            .attr("r", d => config[d.group]?.radius || 10)
            .attr("fill", d => config[d.group]?.color || "#ccc")
            .attr("stroke", "#fff")
            .attr("stroke-width", 1.5);

        // 节点图标
        node.append("text")
            .text(d => config[d.group]?.icon || "")
            .attr("dy", "0.35em")
            .attr("text-anchor", "middle")
            .style("font-size", d => ((config[d.group]?.radius || 10) * 0.7) + "px");

        // 节点标签 - 明确设置浅色填充
        node.append("text")
            .text(d => d.label.length > 20 ? d.label.substring(0, 20) + "..." : d.label)
            .attr("x", d => (config[d.group]?.radius || 10) + 8)
            .attr("y", 4)
            .attr("fill", "#e2e8f0")
            .style("text-shadow", "0 1px 4px rgba(0,0,0,0.9)");

        simulation.on("tick", () => {
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            node
                .attr("transform", d => `translate(${d.x},${d.y})`);
        });

        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x; d.fy = d.y;
        }
        function dragged(event, d) { d.fx = event.x; d.fy = event.y; }
        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null; d.fy = null;
        }

        // 详情面板逻辑
        function showDetails(d) {
            const panel = document.getElementById('details-panel');
            const docEntityMap = __DOC_ENTITY_MAP__;
            
            document.getElementById('panel-type').innerText = config[d.group]?.label || "ENTITY";
            document.getElementById('panel-type').style.color = config[d.group]?.color;
            document.getElementById('panel-title').innerText = d.label;
            
            const connectedIds = new Set();
            connectedIds.add(d.id);
            const connectedNodes = [];
            
            data.links.forEach(l => {
                if(l.source.id === d.id) {
                    connectedIds.add(l.target.id);
                    connectedNodes.push(data.nodes.find(n => n.id === l.target.id));
                }
                if(l.target.id === d.id) {
                    connectedIds.add(l.source.id);
                    connectedNodes.push(data.nodes.find(n => n.id === l.source.id));
                }
            });

            node.style("opacity", n => connectedIds.has(n.id) ? 1 : 0.1);
            link.style("opacity", l => (connectedIds.has(l.source.id) && connectedIds.has(l.target.id)) ? 1 : 0.05);
            link.classed("highlighted", l => (connectedIds.has(l.source.id) && connectedIds.has(l.target.id)));

            // 构建详情内容
            let content = `<div style="margin-bottom:15px;">
                <span style="background:#334155; padding:2px 8px; border-radius:4px; font-size:11px;">连接数: ${d.degree}</span>
                <span style="background:${config[d.group]?.color}30; color:${config[d.group]?.color}; padding:2px 8px; border-radius:4px; font-size:11px; margin-left:6px;">${config[d.group]?.label}</span>
            </div>`;
            
            // 实体类型说明映射
            const typeDescriptions = {
                'keyword': '这是从文献中提取的核心关键词，代表了论文的主要研究主题或概念。',
                'method': '这是论文中使用或提出的研究方法、算法或技术，是理解论文实现思路的关键。',
                'dataset': '这是论文中使用的数据集或基准测试集，对于复现实验和比较研究非常重要。',
                'field': '这是论文所属的研究领域或学科方向，帮助理解论文的学术背景。',
                'application': '这是论文研究成果的应用场景，展示了研究的实际价值和落地方向。',
                'document': '这是您上传的学术文献，系统已自动提取其中的关键实体。'
            };
            
            // 根据节点类型显示不同内容
            if (d.group === 'document') {
                content += `<p style="color:#94a3b8; font-size:12px; margin-bottom:12px;">${typeDescriptions['document']}</p>`;
                const docEntities = docEntityMap[d.label] || docEntityMap[d.id] || {};
                
                // 显示该文献包含的实体概要
                let entitySummary = [];
                if (docEntities.keywords?.length) entitySummary.push(`${docEntities.keywords.length} 个关键词`);
                if (docEntities.methods?.length) entitySummary.push(`${docEntities.methods.length} 个方法`);
                if (docEntities.datasets?.length) entitySummary.push(`${docEntities.datasets.length} 个数据集`);
                if (docEntities.fields?.length) entitySummary.push(`${docEntities.fields.length} 个研究领域`);
                
                if (entitySummary.length > 0) {
                    content += `<div style="background:rgba(99,102,241,0.15); border-radius:8px; padding:12px; margin-bottom:12px;">
                        <div style="color:#a5b4fc; font-size:11px; margin-bottom:6px;">📊 实体统计</div>
                        <div style="color:#e2e8f0; font-size:13px;">${entitySummary.join(' | ')}</div>
                    </div>`;
                }
                
                if (docEntities.keywords && docEntities.keywords.length > 0) {
                    content += `<div style="margin-top:10px;"><strong style="color:#ec4899;">🏷️ 核心关键词:</strong><div style="margin-top:5px; color:#f472b6; font-size:12px;">${docEntities.keywords.slice(0,5).join(', ')}${docEntities.keywords.length > 5 ? '...' : ''}</div></div>`;
                }
                if (docEntities.methods && docEntities.methods.length > 0) {
                    content += `<div style="margin-top:10px;"><strong style="color:#10b981;">⚙️ 使用方法:</strong><div style="margin-top:5px; color:#34d399; font-size:12px;">${docEntities.methods.slice(0,5).join(', ')}${docEntities.methods.length > 5 ? '...' : ''}</div></div>`;
                }
                if (docEntities.datasets && docEntities.datasets.length > 0) {
                    content += `<div style="margin-top:10px;"><strong style="color:#f59e0b;">📊 相关数据集:</strong><div style="margin-top:5px; color:#fbbf24; font-size:12px;">${docEntities.datasets.slice(0,3).join(', ')}${docEntities.datasets.length > 3 ? '...' : ''}</div></div>`;
                }
            } else {
                // 非文档节点 - 显示实体类型说明
                content += `<div style="background:rgba(51, 65, 85, 0.5); border-radius:8px; padding:12px; margin-bottom:12px;">
                    <div style="color:#94a3b8; font-size:11px; margin-bottom:4px;">💡 实体说明</div>
                    <div style="color:#e2e8f0; font-size:12px; line-height:1.5;">${typeDescriptions[d.group] || '这是从文献中提取的实体。'}</div>
                </div>`;
                
                // 查找来源文献
                const sourceDocs = [];
                for (const [docName, entities] of Object.entries(docEntityMap)) {
                    const allEntities = [
                        ...(entities.keywords || []),
                        ...(entities.methods || []),
                        ...(entities.datasets || []),
                        ...(entities.fields || []),
                        ...(entities.applications || [])
                    ];
                    if (allEntities.includes(d.label) || allEntities.includes(d.id)) {
                        sourceDocs.push(docName);
                    }
                }
                
                if (sourceDocs.length > 0) {
                    content += `<div style="margin-bottom:12px;">
                        <div style="color:#94a3b8; font-size:12px; margin-bottom:8px;">📄 <strong>来源文献 (${sourceDocs.length}篇):</strong></div>
                        <div style="background:rgba(99, 102, 241, 0.1); border-radius:8px; padding:10px; max-height:none;">`;
                    sourceDocs.forEach(doc => {
                        content += `<div style="color:#a5b4fc; font-size:12px; margin-bottom:6px; word-break:break-word; line-height:1.4;">• ${doc}</div>`;
                    });
                    content += `</div></div>`;
                    
                    // 查找共现实体（与当前实体在同一文献中出现的其他实体）
                    if (sourceDocs.length > 0) {
                        const coOccurring = {}; // {实体类型: Set<实体名>}
                        sourceDocs.forEach(docName => {
                            const entities = docEntityMap[docName] || {};
                            ['keywords', 'methods', 'datasets'].forEach(type => {
                                (entities[type] || []).forEach(e => {
                                    if (e !== d.label && e !== d.id) {
                                        const typeKey = type.slice(0, -1); // 'keywords' -> 'keyword'
                                        if (!coOccurring[typeKey]) coOccurring[typeKey] = new Set();
                                        coOccurring[typeKey].add(e);
                                    }
                                });
                            });
                        });
                        
                        const coOccurringItems = Object.entries(coOccurring).filter(([_, set]) => set.size > 0);
                        if (coOccurringItems.length > 0) {
                            // 生成唯一ID用于展开/折叠
                            const expandId = 'expand_' + Math.random().toString(36).substr(2, 9);
                            
                            content += `<div style="margin-top:12px; padding-top:12px; border-top:1px solid rgba(255,255,255,0.1);">
                                <div style="color:#94a3b8; font-size:12px; margin-bottom:8px;">🔗 <strong>共现实体:</strong></div>
                                <div style="color:#64748b; font-size:11px; margin-bottom:8px;">在同一文献中经常一起出现的其他实体</div>`;
                            
                            coOccurringItems.forEach(([type, set], typeIdx) => {
                                const typeConfig = config[type] || {};
                                const allItems = Array.from(set);
                                const visibleItems = allItems.slice(0, 4);
                                const hiddenItems = allItems.slice(4);
                                const typeExpandId = expandId + '_' + typeIdx;
                                
                                content += `<div style="margin-bottom:8px;">
                                    <span style="font-size:10px; color:${typeConfig.color || '#94a3b8'};">${typeConfig.icon || ''} ${typeConfig.label || type} (${allItems.length}):</span>
                                    <div id="${typeExpandId}_visible" style="margin-top:3px;">`;
                                
                                // 显示前4个实体（完整显示，不省略）
                                visibleItems.forEach(item => {
                                    content += `<span style="background:${typeConfig.color}15; color:${typeConfig.color}; padding:3px 8px; border-radius:4px; margin:2px; display:inline-block; font-size:10px; word-break:break-word; max-width:100%;">${item}</span>`;
                                });
                                
                                // 如果有更多，添加可展开按钮
                                if (hiddenItems.length > 0) {
                                    content += `<button onclick="document.getElementById('${typeExpandId}_hidden').style.display='block'; this.style.display='none';" style="background:rgba(99,102,241,0.2); color:#a5b4fc; border:1px solid rgba(99,102,241,0.4); border-radius:4px; padding:3px 8px; font-size:10px; cursor:pointer; margin:2px;">展开 +${hiddenItems.length}</button>`;
                                    
                                    content += `</div><div id="${typeExpandId}_hidden" style="display:none; margin-top:4px;">`;
                                    hiddenItems.forEach(item => {
                                        content += `<span style="background:${typeConfig.color}15; color:${typeConfig.color}; padding:3px 8px; border-radius:4px; margin:2px; display:inline-block; font-size:10px; word-break:break-word; max-width:100%;">${item}</span>`;
                                    });
                                    content += `<button onclick="document.getElementById('${typeExpandId}_hidden').style.display='none'; document.getElementById('${typeExpandId}_visible').querySelector('button').style.display='inline-block';" style="background:rgba(100,100,100,0.2); color:#94a3b8; border:1px solid rgba(100,100,100,0.4); border-radius:4px; padding:3px 8px; font-size:10px; cursor:pointer; margin:2px;">收起</button>`;
                                } else {
                                    content += `</div><div style="display:none;">`;
                                }
                                content += `</div></div>`;
                            });
                            content += `</div>`;
                        }
                    }
                } else {
                    content += `<p style="color:#94a3b8; font-size:12px;">此实体尚未关联到具体文献。</p>`;
                }
            }
            
            // 添加知识上下文提示
            // 对于文档节点：基于总连接数
            // 对于实体节点：基于连接的文献数量（更有意义）
            if (d.group === 'document') {
                // 文档节点：原有逻辑
                if (d.degree > 3) {
                    content += `<div style="margin-top:15px; padding:10px; background:linear-gradient(135deg, rgba(99,102,241,0.1), rgba(139,92,246,0.1)); border-radius:8px; border-left:3px solid #8b5cf6;">
                        <div style="color:#a78bfa; font-size:11px; font-weight:600; margin-bottom:4px;">💡 知识洞察</div>
                        <div style="color:#cbd5e1; font-size:11px; line-height:1.4;">该文献与 ${d.degree} 个节点相连，是知识网络中的${ d.degree > 8 ? '核心枢纽' : '重要节点' }。</div>
                    </div>`;
                }
            } else {
                // 实体节点：检查连接的文献数量
                const connectedDocs = connectedNodes.filter(n => n && n.group === 'document');
                const docCount = connectedDocs.length;
                
                if (docCount >= 2) {
                    // 连接多篇文献的实体 - 显示知识洞察
                    const typeLabels = {
                        'keyword': '研究主题',
                        'method': '方法/技术',
                        'dataset': '数据集',
                        'field': '研究领域',
                        'application': '应用场景'
                    };
                    const typeLabel = typeLabels[d.group] || '概念';
                    
                    content += `<div style="margin-top:15px; padding:10px; background:linear-gradient(135deg, rgba(99,102,241,0.1), rgba(139,92,246,0.1)); border-radius:8px; border-left:3px solid #8b5cf6;">
                        <div style="color:#a78bfa; font-size:11px; font-weight:600; margin-bottom:4px;">💡 知识洞察</div>
                        <div style="color:#cbd5e1; font-size:11px; line-height:1.4;">
                            该${typeLabel}出现在 <strong style="color:#fbbf24;">${docCount}</strong> 篇文献中，
                            是这些研究的<strong style="color:#34d399;">共同${typeLabel}</strong>，
                            可能是该领域的${ docCount >= 3 ? '核心概念' : '交叉点' }。
                        </div>
                    </div>`;
                } else if (d.degree > 5) {
                    // 虽然只连接1篇文献，但连接了很多其他实体
                    content += `<div style="margin-top:15px; padding:10px; background:linear-gradient(135deg, rgba(99,102,241,0.1), rgba(139,92,246,0.1)); border-radius:8px; border-left:3px solid #8b5cf6;">
                        <div style="color:#a78bfa; font-size:11px; font-weight:600; margin-bottom:4px;">💡 知识洞察</div>
                        <div style="color:#cbd5e1; font-size:11px; line-height:1.4;">该实体与 ${d.degree} 个节点相连，在其所属文献中是核心概念。</div>
                    </div>`;
                }
            }
            
            document.getElementById('panel-content').innerHTML = content;
            panel.classList.add('open');
            event.stopPropagation();
        }

        function closePanel() {
            document.getElementById('details-panel').classList.remove('open');
            node.style("opacity", 1);
            link.style("opacity", 1).classed("highlighted", false);
        }

        svg.on("click", (e) => {
            if(e.target.tagName === 'svg') closePanel();
        });
        
        // 缩放控制按钮事件
        document.getElementById('zoom-in').addEventListener('click', () => {
            svg.transition().duration(300).call(zoom.scaleBy, 1.5);
        });
        document.getElementById('zoom-out').addEventListener('click', () => {
            svg.transition().duration(300).call(zoom.scaleBy, 0.67);
        });
        document.getElementById('zoom-reset').addEventListener('click', () => {
            svg.transition().duration(500).call(zoom.transform, d3.zoomIdentity);
        });
    </script>
</body>
</html>
"""

def nx_graph_to_d3_data(nx_graph: nx.Graph) -> Dict[str, Any]:
    data = {"nodes": [], "links": []}
    if not nx_graph: return data

    for node_id, attrs in nx_graph.nodes(data=True):
        data["nodes"].append({
            "id": str(node_id),
            "label": attrs.get("label", str(node_id)),
            "group": attrs.get("node_type", "keyword"),
            "degree": nx_graph.degree(node_id)
        })

    for u, v, attrs in nx_graph.edges(data=True):
        data["links"].append({
            "source": str(u),
            "target": str(v),
            "value": attrs.get("weight", 1)
        })
    return data

def render_graph_in_streamlit(nx_graph: nx.Graph, height: int = 750, key: str = "knowledge_graph", doc_entity_map: Dict[str, Any] = None) -> None:
    if nx_graph is None or nx_graph.number_of_nodes() == 0:
        st.info("📊 暂无知识图谱数据。请先上传文档并进行实体提取。")
        return
    
    # 确保 doc_entity_map 不为 None
    if doc_entity_map is None:
        doc_entity_map = {}
    
    # 节点类型过滤器
    st.markdown("**🎛️ 节点过滤器** - 选择要显示的节点类型")
    
    # 获取所有可用的节点类型
    all_types = list(NODE_CONFIG.keys())
    type_labels = {k: v['label'] for k, v in NODE_CONFIG.items()}
    
    # 使用 session state 保存选中状态
    filter_key = f"{key}_type_filter"
    if filter_key not in st.session_state:
        # 默认显示文档和关键词、方法
        st.session_state[filter_key] = ["document", "keyword", "method"]
    
    # 创建多选框
    selected_types = st.multiselect(
        "选择要显示的节点类型",
        options=all_types,
        default=st.session_state[filter_key],
        format_func=lambda x: f"{NODE_CONFIG[x]['icon']} {type_labels[x]}",
        key=f"{key}_multiselect",
        help="取消勾选某个类型可以隐藏对应节点，减少视觉混乱"
    )
    
    # 保存选中状态
    st.session_state[filter_key] = selected_types
    
    # 快捷按钮
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("📄 仅文档", key=f"{key}_only_doc", use_container_width=True):
            st.session_state[filter_key] = ["document"]
            st.rerun()
    with col2:
        if st.button("🔗 核心关联", key=f"{key}_core", use_container_width=True):
            st.session_state[filter_key] = ["document", "keyword", "method"]
            st.rerun()
    with col3:
        if st.button("🌐 显示全部", key=f"{key}_show_all", use_container_width=True):
            st.session_state[filter_key] = all_types
            st.rerun()
    
    st.markdown("---")
    
    # 过滤节点和边
    d3_data = nx_graph_to_d3_data_filtered(nx_graph, selected_types)
    
    if not d3_data["nodes"]:
        st.warning("当前过滤条件下没有节点，请选择更多节点类型。")
        return
    
    legend_items = ""
    for k, v in NODE_CONFIG.items():
        if k in selected_types:
            legend_items += f"""
            <div class='legend-item'>
                <div class='legend-dot' style='background:{v['color']}'></div>
                <span>{v['label']}</span>
            </div>
            """

    # 使用 .replace() 替代 .format()，避免与 JS/CSS 中的 { } 冲突
    html_content = D3_TEMPLATE.replace("__GRAPH_DATA__", json.dumps(d3_data)) \
                              .replace("__NODE_CONFIG__", json.dumps(NODE_CONFIG)) \
                              .replace("__NODE_COUNT__", str(len(d3_data["nodes"]))) \
                              .replace("__EDGE_COUNT__", str(len(d3_data["links"]))) \
                              .replace("__LEGEND_HTML__", legend_items) \
                              .replace("__DOC_ENTITY_MAP__", json.dumps(doc_entity_map))

    components.html(html_content, height=height, scrolling=False)


def nx_graph_to_d3_data_filtered(nx_graph: nx.Graph, selected_types: list) -> Dict[str, Any]:
    """
    将 NetworkX 图转换为 D3.js 数据格式，支持按节点类型过滤
    
    Args:
        nx_graph: NetworkX 图
        selected_types: 要显示的节点类型列表
        
    Returns:
        过滤后的 D3 数据字典
    """
    data = {"nodes": [], "links": []}
    if not nx_graph:
        return data
    
    # 收集符合条件的节点 ID
    valid_node_ids = set()
    
    for node_id, attrs in nx_graph.nodes(data=True):
        node_type = attrs.get("node_type", "keyword")
        if node_type in selected_types:
            data["nodes"].append({
                "id": str(node_id),
                "label": attrs.get("label", str(node_id)),
                "group": node_type,
                "degree": nx_graph.degree(node_id)
            })
            valid_node_ids.add(str(node_id))
    
    # 只保留两端都在有效节点中的边
    for u, v, attrs in nx_graph.edges(data=True):
        if str(u) in valid_node_ids and str(v) in valid_node_ids:
            data["links"].append({
                "source": str(u),
                "target": str(v),
                "value": attrs.get("weight", 1)
            })
    
    return data

def render_graph_statistics(stats: Dict[str, Any]) -> None:
    """
    渲染图谱统计信息
    重构版本：可点击的统计卡片 + 深色/浅色模式兼容 + 可展开实体列表
    """
    
    # 注入 CSS 来移除 Streamlit components.html 创建的 iframe 边框
    # 这是解决白色边框问题的关键 - 覆盖所有可能的容器和 iframe 样式
    st.markdown("""
    <style>
        /* === 彻底移除所有 iframe 的边框和背景 === */
        iframe {
            border: none !important;
            background: transparent !important;
            box-shadow: none !important;
            outline: none !important;
        }
        
        /* 针对 Streamlit 的各种组件容器 */
        .stCustomComponentV1,
        .stCustomComponentV1 > div,
        .stCustomComponentV1 > iframe,
        [data-testid="stCustomComponentV1"],
        [data-testid="stCustomComponentV1"] > div,
        [data-testid="stCustomComponentV1"] > iframe {
            border: none !important;
            background: transparent !important;
            box-shadow: none !important;
            outline: none !important;
        }
        
        /* 针对可能嵌套的 iframe 容器 */
        .element-container iframe,
        .stMarkdown + div iframe,
        div[data-testid] iframe {
            border: none !important;
            background: transparent !important;
        }
        
        /* 移除可能的白色边框来源 - 深色主题覆盖 */
        [data-theme="dark"] iframe,
        [data-theme="dark"] .stCustomComponentV1,
        .stApp[data-theme="dark"] iframe {
            border: none !important;
            background: transparent !important;
        }
        
        /* 额外的安全措施：覆盖任何 border 样式 */
        .stCustomComponentV1 *,
        [data-testid="stCustomComponentV1"] * {
            border-color: transparent !important;
        }
    </style>
    """, unsafe_allow_html=True)
    # 统计卡片 - 使用 Streamlit 原生组件以支持交互
    cols = st.columns(4)
    
    # 获取所有实体列表
    all_keywords = stats.get("all_keywords", [])
    all_methods = stats.get("all_methods", [])
    all_datasets = stats.get("all_datasets", [])
    all_fields = stats.get("all_fields", [])
    
    metrics = [
        ("📄 文档", stats.get("document_count", 0), "#6366f1", "documents", stats.get("documents", [])),
        ("🏷️ 关键词", len(all_keywords), "#ec4899", "keywords", all_keywords),
        ("⚙️ 方法", len(all_methods), "#10b981", "methods", all_methods),
        ("📊 数据集", len(all_datasets), "#f59e0b", "datasets", all_datasets),
    ]
    
    for col, (label, count, color, key, entities) in zip(cols, metrics):
        with col:
            # 使用 st.metric 简洁显示，同时支持浅色/深色模式
            st.metric(label=label, value=count)
    
    # 可展开的完整实体列表
    st.markdown("---")
    st.markdown("### 📋 完整实体列表")
    st.caption("点击下方分类查看完整实体列表")
    
    # 关键词列表
    if all_keywords:
        with st.expander(f"🏷️ 全部关键词 ({len(all_keywords)}个)", expanded=False):
            # 使用多列布局
            kw_cols = st.columns(3)
            for idx, (kw, count) in enumerate(all_keywords):
                kw_cols[idx % 3].markdown(f"• **{kw}** ({count})")
    
    # 方法列表
    if all_methods:
        with st.expander(f"⚙️ 全部方法 ({len(all_methods)}个)", expanded=False):
            mt_cols = st.columns(3)
            for idx, (mt, count) in enumerate(all_methods):
                mt_cols[idx % 3].markdown(f"• **{mt}** ({count})")
    
    # 数据集列表
    if all_datasets:
        with st.expander(f"📊 全部数据集 ({len(all_datasets)}个)", expanded=False):
            ds_cols = st.columns(3)
            for idx, (ds, count) in enumerate(all_datasets):
                ds_cols[idx % 3].markdown(f"• **{ds}** ({count})")
    
    # 领域列表
    if all_fields:
        with st.expander(f"🎓 全部研究领域 ({len(all_fields)}个)", expanded=False):
            fd_cols = st.columns(3)
            for idx, (fd, count) in enumerate(all_fields):
                fd_cols[idx % 3].markdown(f"• **{fd}** ({count})")
    
    # ===== 核心实体详情（保留，但修复样式）=====
    st.markdown("---")
    st.markdown("### 🔥 核心实体详情")
    
    css = """
    <style>
        /* 去除 iframe 默认边框 */
        iframe {
            border: none !important;
        }
        
        /* 深色模式玻璃拟态风格 */
        .kg-stats-container {
            font-family: "Microsoft YaHei", system-ui, sans-serif;
            background: rgba(30, 41, 59, 0.95);
            backdrop-filter: blur(16px);
            border: none;
            border-radius: 16px;
            padding: 20px;
            color: #f1f5f9;
            margin: 0;
        }
        
        .section-title {
            font-weight: bold;
            color: #e2e8f0;
            margin-bottom: 12px;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .tag-container { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
        .tag {
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            border: 1px solid transparent;
            cursor: pointer;
            transition: all 0.2s;
            max-width: 100%;
            word-break: break-word;
        }
        .tag:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        /* 深色模式下的标签配色 */
        .tag-kw { background: rgba(236, 72, 153, 0.2); color: #f472b6; border-color: rgba(236, 72, 153, 0.4); }
        .tag-mt { background: rgba(16, 185, 129, 0.2); color: #34d399; border-color: rgba(16, 185, 129, 0.4); }
        .tag-ds { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border-color: rgba(245, 158, 11, 0.4); }
        .tag-fd { background: rgba(139, 92, 246, 0.2); color: #a78bfa; border-color: rgba(139, 92, 246, 0.4); }
        .tag-app { background: rgba(6, 182, 212, 0.2); color: #22d3ee; border-color: rgba(6, 182, 212, 0.4); }
        
        .tag-count {
            opacity: 0.7;
            font-size: 11px;
        }
        
        .entity-section {
            margin-bottom: 20px;
        }
        
        .two-column {
            display: flex;
            gap: 20px;
        }
        .two-column > div {
            flex: 1;
        }
    </style>
    """
    
    def build_tags(items, tag_class):
        """构建实体标签HTML，空数据返回空字符串以隐藏整个分类"""
        if not items:
            return ""
        tags = ""
        for item, count in items[:10]:  # 只显示前10个
            tags += f"<span class='tag {tag_class}'>{item} <span class='tag-count'>({count})</span></span>"
        if len(items) > 10:
            tags += f"<span class='tag' style='background: rgba(100,100,100,0.3); color: #94a3b8;'>+{len(items)-10} 更多...</span>"
        return tags
    
    # 构建各分类的标签
    keywords_html = build_tags(stats.get("top_keywords", []), "tag-kw")
    methods_html = build_tags(stats.get("top_methods", []), "tag-mt")
    datasets_html = build_tags(stats.get("top_datasets", []), "tag-ds")
    fields_html = build_tags(stats.get("top_fields", []), "tag-fd")
    
    # 构建条件渲染的 HTML 部分
    keywords_section = f"""
        <div class="entity-section">
            <div class="section-title">📌 高频关键词 (Top Keywords)</div>
            <div class="tag-container">{keywords_html}</div>
        </div>
    """ if keywords_html else ""
    
    methods_section = f"""
        <div style="flex:1;">
            <div class="section-title">🛠️ 核心方法 (Methods)</div>
            <div class="tag-container">{methods_html}</div>
        </div>
    """ if methods_html else ""
    
    datasets_section = f"""
        <div style="flex:1;">
            <div class="section-title">📊 数据集 (Datasets)</div>
            <div class="tag-container">{datasets_html}</div>
        </div>
    """ if datasets_html else ""
    
    fields_section = f"""
        <div style="flex:1;">
            <div class="section-title">🎓 研究领域 (Fields)</div>
            <div class="tag-container">{fields_html}</div>
        </div>
    """ if fields_html else ""
    
    # 两列布局只在有内容时显示
    two_column_content = ""
    if methods_section or datasets_section:
        two_column_content = f"""
        <div class="two-column">
            {methods_section}
            {datasets_section}
        </div>
        """
    
    # 只在有内容时显示核心实体详情区块
    if keywords_section or two_column_content or fields_section:
        content_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                html, body {{
                    margin: 0;
                    padding: 0;
                    background: transparent;
                }}
            </style>
            {css}
        </head>
        <body style="margin: 0; padding: 0; background: transparent;">
            <div class="kg-stats-container">
                {keywords_section}
                {two_column_content}
                {fields_section}
            </div>
        </body>
        </html>
        """
        components.html(content_html, height=350, scrolling=True)

def render_legend() -> None:
    pass


def render_entity_source_expanders(stats: Dict[str, Any], knowledge_graph) -> None:
    """
    渲染可展开的实体列表，点击实体可查看来源文献
    
    Args:
        stats: 图谱统计信息
        knowledge_graph: KnowledgeGraph 实例，用于查询实体来源
    """
    st.markdown("### 📚 实体详情与来源追溯")
    st.caption("点击实体标签查看其来源文献")
    
    # 定义实体类型配置
    entity_types = [
        ("keywords", "all_keywords", "🏷️ 关键词", "#ec4899"),
        ("methods", "all_methods", "⚙️ 方法/技术", "#10b981"),
        ("datasets", "all_datasets", "📊 数据集", "#f59e0b"),
        ("fields", "all_fields", "🎓 研究领域", "#8b5cf6"),
        ("applications", "all_applications", "💻 应用场景", "#06b6d4"),
    ]
    
    for etype, stats_key, label, color in entity_types:
        entities = stats.get(stats_key, [])
        if not entities:
            continue
        
        with st.expander(f"{label} ({len(entities)}个)", expanded=False):
            # 使用列布局显示实体标签
            cols = st.columns(3)
            for idx, (entity_name, count) in enumerate(entities):
                col = cols[idx % 3]
                
                # 每个实体是一个小卡片
                with col:
                    # 创建一个小型的 expander 显示来源
                    entity_key = f"entity_{etype}_{idx}"
                    
                    # 使用 HTML 显示实体标签
                    col.markdown(f"""
                    <div style="
                        background: rgba(51, 65, 85, 0.4);
                        border: 1px solid {color}40;
                        border-radius: 8px;
                        padding: 8px 12px;
                        margin-bottom: 8px;
                        cursor: pointer;
                    ">
                        <div style="color: {color}; font-weight: 600; font-size: 13px;">{entity_name}</div>
                        <div style="color: #94a3b8; font-size: 11px;">出现 {count} 次</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # 查询来源文献
                    if knowledge_graph:
                        sources = knowledge_graph.get_entity_sources(entity_name)
                        if sources:
                            with st.popover(f"📄 来源 ({len(sources)})"):
                                st.markdown("**来源文献:**")
                                for src in sources:
                                    st.markdown(f"- 📄 {src}")


def render_entity_source_buttons(stats: Dict[str, Any], knowledge_graph) -> None:
    """
    使用 Streamlit 按钮和会话状态渲染可点击的实体标签
    
    Args:
        stats: 图谱统计信息
        knowledge_graph: KnowledgeGraph 实例
    """
    # 初始化会话状态
    if "selected_entity" not in st.session_state:
        st.session_state.selected_entity = None
    
    st.markdown("### 📚 点击实体查看来源")
    
    # 获取所有关键词和方法
    keywords = stats.get("all_keywords", [])[:15]  # 限制显示数量
    methods = stats.get("all_methods", [])[:10]
    
    # 预计算每个实体的来源文献数量（修复：显示来源文献数而非出现次数）
    def get_source_count(entity_name: str) -> int:
        if knowledge_graph:
            return len(knowledge_graph.get_entity_sources(entity_name))
        return 0
    
    if keywords:
        st.markdown("**🏷️ 高频关键词:**")
        cols = st.columns(6)
        for idx, (name, _count) in enumerate(keywords):
            with cols[idx % 6]:
                # 显示来源文献数量而非出现次数
                source_count = get_source_count(name)
                if st.button(f"{name} ({source_count})", key=f"kw_{idx}", use_container_width=True):
                    st.session_state.selected_entity = name
    
    if methods:
        st.markdown("**⚙️ 核心方法:**")
        cols = st.columns(6)
        for idx, (name, _count) in enumerate(methods):
            with cols[idx % 6]:
                source_count = get_source_count(name)
                if st.button(f"{name} ({source_count})", key=f"mt_{idx}", use_container_width=True):
                    st.session_state.selected_entity = name
    
    # 显示选中实体的来源
    if st.session_state.selected_entity and knowledge_graph:
        st.markdown("---")
        entity = st.session_state.selected_entity
        sources = knowledge_graph.get_entity_sources(entity)
        
        st.markdown(f"### 🔍 「{entity}」的来源文献")
        if sources:
            for src in sources:
                st.markdown(f"- 📄 **{src}**")
        else:
            st.info("未找到来源文献")