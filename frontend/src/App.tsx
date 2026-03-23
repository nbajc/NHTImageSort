import React, { useState, useEffect } from 'react';
import { Play, Loader2, FolderOpen, FolderOutput, Tags, Settings, Image as ImageIcon, AlertCircle, Trash2, Pencil, Search, X } from 'lucide-react';
import { API_URL } from './config';
import CloudBanner from './CloudBanner';

interface JobState {
  status: 'idle' | 'starting' | 'running' | 'completed' | 'error';
  current_file: string | null;
  description: string | null;
  category: string | null;
  processed: number;
  total: number;
  results: any[];
  error: string | null;
}

function App() {
  const [source, setSource] = useState('C:/path/to/images');
  const [target, setTarget] = useState('C:/path/to/images_sorted');
  const [categories, setCategories] = useState(() => localStorage.getItem('nexus_categories') || 'Interior, Exterior, Residential, Hospitality, Institutional');
  const [visionModel, setVisionModel] = useState('llava');
  const [textModel, setTextModel] = useState('llama3');
  const [dryRun, setDryRun] = useState(false);
  const [projectTag, setProjectTag] = useState('');
  const [removePath, setRemovePath] = useState('');
  
  // Search State
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[] | null>(null);

  // Catalog State
  const [catalog, setCatalog] = useState<any[]>([]);

  const fetchCatalog = async () => {
    try {
      const res = await fetch(`${API_URL}/api/search`);
      const data = await res.json();
      if (data.results) setCatalog(data.results);
    } catch (err) {
      console.error("Failed to fetch catalog");
    }
  };

  useEffect(() => {
    fetchCatalog();
  }, []);

  // Modal State
  const [modalImage, setModalImage] = useState<any>(null);
  const [editDesc, setEditDesc] = useState('');
  const [isRemovingDoubles, setIsRemovingDoubles] = useState(false);
  
  // Toast State
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const [jobState, setJobState] = useState<JobState>({
    status: 'idle',
    current_file: null,
    description: null,
    category: null,
    processed: 0,
    total: 0,
    results: [],
    error: null
  });

  const pollInterval = React.useRef<number | null>(null);

  const [activeTab, setActiveTab] = useState('All');

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/status`);
      const data = await res.json();
      setJobState(data);
      if (data.status === 'completed' || data.status === 'error') {
        if (pollInterval.current) clearInterval(pollInterval.current);
      }
    } catch (err) {
      console.error("Failed to fetch status");
    }
  };

  useEffect(() => {
    fetchStatus();
    return () => {
      if (pollInterval.current) clearInterval(pollInterval.current);
    };
  }, []);

  useEffect(() => {
    if (jobState.status === 'completed') {
      fetchCatalog();
    }
  }, [jobState.status]);

  // Search Debounce Effect
  useEffect(() => {
    if (searchQuery.trim().length > 0) {
      const delayDebounceFn = setTimeout(() => {
        fetch(`${API_URL}/api/search?q=${encodeURIComponent(searchQuery)}`)
          .then(res => res.json())
          .then(data => {
            if (data.results) {
              setSearchResults(data.results);
            }
          })
          .catch(err => console.error("Search failed", err));
      }, 300);
      return () => clearTimeout(delayDebounceFn);
    } else {
      setSearchResults(null);
    }
  }, [searchQuery]);

  const handleStart = async () => {
    if (jobState.status === 'running' || jobState.status === 'starting') return;
    
    try {
      localStorage.setItem('nexus_categories', categories);
      const catArray = categories.split(',').map(c => c.trim()).filter(c => c);
      await fetch(`${API_URL}/api/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          source,
          target,
          categories: catArray,
          vision_model: visionModel,
          text_model: textModel,
          dry_run: dryRun,
          project_tag: projectTag
        })
      });
      
      setJobState(prev => ({ ...prev, status: 'starting', processed: 0, results: [], error: null }));
      setSearchResults(null);
      setSearchQuery('');
      
      if (pollInterval.current) clearInterval(pollInterval.current);
      pollInterval.current = window.setInterval(fetchStatus, 1000);
    } catch (err) {
      setJobState(prev => ({ ...prev, status: 'error', error: "Failed to connect to API" }));
    }
  };

  const handleDeleteFolder = async () => {
    if (!removePath) return;
    if (!confirm(`Are you sure you want to delete folder: ${removePath}?`)) return;
    try {
      const res = await fetch(`${API_URL}/api/delete_folder`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: removePath })
      });
      if (res.ok) {
        alert("Folder deleted successfully.");
        fetchCatalog();
        if (searchQuery) setSearchQuery(prev => prev + ' ');
      }
      else alert("Error deleting folder.");
    } catch {
      alert("Failed to connect to API");
    }
  };

  const handleRemoveDoubles = async () => {
    if (!confirm("This will permanently scan and delete all physically identical images from your sorted target folders. Only one exact copy will be preserved. Continue?")) return;
    try {
      setIsRemovingDoubles(true);
      const res = await fetch(`${API_URL}/api/remove_doubles`, {
        method: 'POST'
      });
      const data = await res.json();
      if (res.ok) {
        alert(data.message);
        fetchCatalog(); 
      } else {
        alert("Error: " + data.error);
      }
    } catch {
      alert("Failed to connect to API");
    } finally {
      setIsRemovingDoubles(false);
    }
  };

  const handleDeleteItem = async (filePath: string) => {
    if (!confirm(`Delete image ${filePath}?`)) return;
    try {
      const res = await fetch(`${API_URL}/api/delete_item`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: filePath })
      });
      if (res.ok) {
        if (searchResults) {
          setSearchResults(prev => prev ? prev.filter(r => (r.new_path || r.file) !== filePath) : null);
        }
        setCatalog(prev => prev.filter(r => (r.new_path || r.file) !== filePath));
        setJobState(prev => ({
          ...prev,
          results: prev.results.filter(r => (r.new_path || r.file) !== filePath)
        }));
      }
    } catch {
      alert("Failed to delete item");
    }
  };

  const handleSaveEdit = async (filePath: string) => {
    if (!filePath) return;
    try {
      let updatedProjectTag: string | undefined = undefined;
      if (!dryRun) {
        const res = await fetch(`${API_URL}/api/update_item`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: filePath, description: editDesc })
        });
        if (!res.ok) {
           alert("Failed to update description file.");
           return;
        }
        const data = await res.json();
        updatedProjectTag = data.project_tag;
      }
      
      const updateObj = (r: any) => {
        if ((r.new_path || r.original_path || r.file) === filePath) {
          const newR = { ...r, description: editDesc };
          if (updatedProjectTag !== undefined && updatedProjectTag !== null) {
            newR.project_tag = updatedProjectTag;
          }
          return newR;
        }
        return r;
      };

      if (searchResults) {
        setSearchResults(prev => prev ? prev.map(updateObj) : null);
      }
      setCatalog(prev => prev.map(updateObj));
      setJobState(prev => ({ ...prev, results: prev.results.map(updateObj) }));
      
      // Update modal image if it's the one being edited
      setModalImage((prev: any) => prev && (prev.new_path || prev.original_path || prev.file) === filePath ? updateObj(prev) : prev);
      
      showToast("Description saved successfully!");
    } catch {
      alert("Failed to update description");
    }
  };

  const progressPercent = jobState.total > 0 ? (jobState.processed / jobState.total) * 100 : 0;

  // We have combined catalog and job results
  const combinedResults = [...jobState.results, ...catalog].filter((v, i, a) => a.findIndex(t => (t.new_path || t.file) === (v.new_path || v.file)) === i);
  
  // Dynamically extract all unique categories that have ever been used or configured
  const dynamicCategories = Array.from(new Set([
    ...categories.split(',').map(c => c.trim()).filter(c => c),
    ...combinedResults.map(r => r.category).filter(c => c)
  ])).sort();

  // Full Catalogue Filters
  const displayedCatalog = activeTab === 'All' 
    ? combinedResults 
    : combinedResults.filter((r: any) => r.category && r.category.toLowerCase().includes(activeTab.toLowerCase()));

  // Render Image Card helper
  const renderImageCard = (res: any, idx: number) => {
    const itemId = res.new_path || res.file;
    return (
      <div key={`${itemId}-${idx}`} 
           onClick={() => { setModalImage(res); setEditDesc(res.description); }} 
           className="bg-black/30 rounded-xl overflow-hidden shadow-lg border border-[#ffffff0a] flex flex-col hover:border-[#ffffff30] hover:ring-1 hover:ring-primary/50 transition-all cursor-pointer group/card relative min-h-[260px]">
        
        <div className="h-[120px] bg-[#110e1a] w-full relative overflow-hidden flex items-center justify-center border-b border-white/5">
          {!res.placeholder && (res.new_path || res.id) ? (
            <img src={res.id ? `${API_URL}/api/image?id=${res.id}` : `${API_URL}/api/image?path=${encodeURIComponent(res.new_path)}`} className="w-full h-full object-cover group-hover/card:scale-105 transition-transform duration-700" alt="thumbnail" />
          ) : (
            <ImageIcon className="w-8 h-8 text-white/20" />
          )}
        </div>
        
        {/* Action Buttons */}
        <div className="absolute top-2 right-2 flex gap-1 opacity-0 group-hover/card:opacity-100 transition-opacity">
          <button onClick={(e) => { e.stopPropagation(); handleDeleteItem(itemId); }} className="p-1.5 bg-red-500/20 hover:bg-red-500/50 rounded border border-red-500/30 text-red-300 hover:text-white transition-colors backdrop-blur-md shadow-lg">
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="p-3.5 flex-1 flex flex-col pointer-events-none">
          <div className="mb-2 uppercase text-[0.55rem] font-extrabold tracking-widest text-secondary self-start px-2 py-0.5 rounded-md bg-secondary/10 border border-secondary/20 truncate max-w-full">
            {res.category}
          </div>
          
          <div className="flex flex-wrap gap-1 mb-1 -mt-1">
            {res.project_tag && res.project_tag.split(',').map((t: string, i: number) => (
              <div key={i} className="text-primary text-[0.65rem] font-bold truncate max-w-full inline-block">#{t.trim()}</div>
            ))}
          </div>

          <p className="text-[0.65rem] text-textMuted line-clamp-4 leading-relaxed flex-1 font-medium group-hover/card:text-white/80 transition-colors pointer-events-none">
            {res.description}
          </p>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen font-sans p-6 md:p-12 selection:bg-primary selection:text-white">
      <CloudBanner />
      <header className="mb-10 text-center md:text-left flex flex-col md:flex-row items-center md:items-start gap-6 lg:gap-8">
        <div className="w-24 h-24 md:w-32 md:h-32 bg-black/40 border border-primary/20 rounded-xl p-3 shadow-[0_0_25px_rgba(236,72,153,0.2)] shrink-0 flex items-center justify-center">
          <img src="/logo.jpg" className="w-full h-full object-contain drop-shadow-[0_0_10px_rgba(236,72,153,0.4)]" alt="Nexus Hestia Logo" />
        </div>
        <div className="flex flex-col justify-center pt-2">
          <h1 className="text-4xl md:text-[3.5rem] leading-none font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-primary to-secondary mb-2">
            Nexus Hestia
          </h1>
          <h2 className="text-2xl md:text-3xl text-white mb-2 pb-1 font-extrabold uppercase tracking-wide">
            Image Sorter
          </h2>
          <p className="text-textMuted text-lg tracking-wide uppercase text-[0.85rem] font-semibold opacity-80">Intelligent local image categorization</p>
        </div>
      </header>

      <main className="max-w-[1400px] mx-auto grid grid-cols-1 lg:grid-cols-12 gap-8">
        
        {/* Conf Panel */}
        <section className="lg:col-span-4 space-y-6">
          
          {/* Search Database Box */}
          <div className="glass-panel p-6 shadow-2xl ring-1 ring-primary/20">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2 text-white">
              <Search className="w-5 h-5 text-primary" /> Search Catalogue
            </h2>
            <div className="relative">
              <input 
                type="text" 
                value={searchQuery} 
                onChange={e => setSearchQuery(e.target.value)}
                placeholder="Search descriptions, tags, files..."
                className="w-full bg-black/50 border border-white/20 rounded-lg pl-10 pr-4 py-3 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary transition-all text-white shadow-inner"
              />
              <Search className="w-5 h-5 text-white/40 absolute left-3 top-3.5" />
            </div>
            {searchQuery.length > 0 && searchResults !== null && (
              <div className="mt-3 text-sm text-textMuted flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-primary animate-pulse"></span>
                Found {searchResults.length} matching entries
              </div>
            )}
          </div>

          <div className="glass-panel p-6">
            <h2 className="text-xl font-bold mb-6 flex items-center gap-2 border-b border-white/10 pb-4 text-white">
              <Settings className="w-5 h-5 text-primary" /> Configuration
            </h2>
            
            <div className="space-y-4">
              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-textMuted mb-1"><FolderOpen className="w-4 h-4"/> Source Dir</label>
                <input type="text" value={source} onChange={e => setSource(e.target.value)} className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 focus:outline-none focus:border-primary transition-colors text-white" />
              </div>
              
              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-textMuted mb-1"><FolderOutput className="w-4 h-4"/> Target Dir</label>
                <input type="text" value={target} onChange={e => setTarget(e.target.value)} className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 focus:outline-none focus:border-primary transition-colors text-white" />
              </div>

              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-textMuted mb-1">Project Tag</label>
                <input type="text" value={projectTag} onChange={e => setProjectTag(e.target.value)} placeholder="e.g. Campaign2024" className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 focus:outline-none focus:border-primary transition-colors text-white" />
              </div>

              <div>
                <label className="flex items-center gap-2 text-sm font-medium text-textMuted mb-1"><Tags className="w-4 h-4"/> Categories (comma-separated)</label>
                <input type="text" value={categories} onChange={e => setCategories(e.target.value)} className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2 focus:outline-none focus:border-primary transition-colors text-white" />
              </div>

              <div className="grid grid-cols-2 gap-4 pt-2">
                <div>
                  <label className="block text-xs font-medium text-textMuted mb-1">Vision Model</label>
                  <input type="text" value={visionModel} onChange={e => setVisionModel(e.target.value)} className="w-full bg-black/40 border border-white/10 rounded px-3 py-1.5 text-sm outline-none text-white" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-textMuted mb-1">Text Model</label>
                  <input type="text" value={textModel} onChange={e => setTextModel(e.target.value)} className="w-full bg-black/40 border border-white/10 rounded px-3 py-1.5 text-sm outline-none text-white" />
                </div>
              </div>

              <label className="flex items-center gap-3 pt-2 cursor-pointer group">
                <div className="relative">
                  <input type="checkbox" checked={dryRun} onChange={e => setDryRun(e.target.checked)} className="sr-only peer"/>
                  <div className="w-10 h-6 bg-black/50 rounded-full peer-checked:bg-secondary transition-colors border border-white/10"></div>
                  <div className="absolute left-1 top-1 w-4 h-4 bg-textMuted rounded-full transition-transform peer-checked:translate-x-4 peer-checked:bg-white"></div>
                </div>
                <span className="text-sm font-medium text-textMuted group-hover:text-white transition-colors">Dry Run Mode</span>
              </label>

              <button 
                onClick={handleStart}
                disabled={jobState.status === 'running' || jobState.status === 'starting'}
                className="w-full mt-4 py-3 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-bold flex justify-center items-center gap-2 hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {(jobState.status === 'running' || jobState.status === 'starting') ? (
                  <><Loader2 className="w-5 h-5 animate-spin"/> Processing...</>
                ) : (
                  <><Play className="w-5 h-5"/> Start Sorting</>
                )}
              </button>
            </div>
          </div>

          <div className="glass-panel p-6 mt-6 border-red-500/20">
            <h3 className="text-sm font-bold text-red-400 mb-3 flex items-center gap-2">
               Remove from Catalogue
            </h3>
            <input 
              type="text" 
              value={removePath}
              onChange={e => setRemovePath(e.target.value)}
              placeholder="Full path to target folder"
              className="w-full bg-black/30 border border-white/10 rounded px-3 py-2 text-sm text-textMain mb-3 focus:outline-none focus:border-red-500/50 transition-colors"
            />
            <button 
              onClick={handleDeleteFolder} 
              className="w-full bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 py-2 rounded font-bold text-sm transition-all flex items-center justify-center gap-2">
              <Trash2 className="w-4 h-4" /> Delete Category / Folder
            </button>

            <h3 className="text-sm font-bold text-red-400 mb-3 flex items-center gap-2 mt-6 pt-4 border-t border-red-500/20">
               Clean Storage
            </h3>
            <button 
              onClick={handleRemoveDoubles} 
              disabled={isRemovingDoubles}
              className="w-full bg-red-500/10 hover:bg-red-500/20 disabled:opacity-50 text-red-400 border border-red-500/20 py-2 rounded font-bold text-sm transition-all flex items-center justify-center gap-2">
              {isRemovingDoubles ? <Loader2 className="w-4 h-4 animate-spin"/> : <Trash2 className="w-4 h-4" />} {isRemovingDoubles ? "Scanning..." : "Remove Exact Doubles"}
            </button>
          </div>
        </section>

        {/* Status & Results Layer */}
        <section className="lg:col-span-8 flex flex-col gap-6">
          
          <div className="glass-panel p-6 flex flex-col gap-4">
            <h2 className="text-xl font-bold flex items-center justify-between border-b border-white/10 pb-4 text-white">
              <span>Job Status Overview</span>
              <span className={`text-sm px-3 py-1 rounded-full border font-semibold tracking-wide ${jobState.status === 'running' ? 'bg-primary/20 border-primary/50 text-primary animate-pulse' : jobState.status === 'error' ? 'bg-red-500/10 border-red-500 text-red-500' : 'bg-white/5 border-white/10 text-textMuted'}`}>
                {jobState.status.toUpperCase()}
              </span>
            </h2>

            {jobState.error && (
              <div className="bg-red-500/10 border border-red-500/50 text-red-400 p-4 rounded-lg flex gap-3 text-sm">
                <AlertCircle className="w-5 h-5 shrink-0"/> {jobState.error}
              </div>
            )}

            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-textMuted">Job Progress</span>
                <span className="font-mono text-white">{jobState.processed} / {jobState.total || '?'}</span>
              </div>
              <div className="h-2 w-full bg-black/50 rounded-full overflow-hidden border border-white/5">
                <div 
                  className="h-full bg-gradient-to-r from-primary to-secondary transition-all duration-500 ease-out"
                  style={{ width: `${progressPercent}%` }}
                ></div>
              </div>
            </div>
          </div>

          {/* Independent Search Results Panel pops up here! */}
          {searchQuery.length > 0 && searchResults !== null && (
            <div className="glass-panel p-6 flex-1 flex flex-col border border-primary/30 shadow-[0_0_30px_rgba(236,72,153,0.15)] transition-all animate-in fade-in duration-500">
              <div className="border-b border-white/10 pb-4 mb-4 flex justify-between items-center">
                <h2 className="text-xl font-bold flex items-center gap-2 text-white">
                  <Search className="w-5 h-5 text-primary" /> Active Search Results 
                </h2>
                <button onClick={() => { setSearchQuery(''); setSearchResults(null); }} className="text-xs px-3 py-1 bg-white/5 hover:bg-white/10 rounded-full text-textMuted hover:text-white transition-colors">Clear Search</button>
              </div>
              
              {searchResults.length === 0 ? (
                <div className="text-center py-10 text-textMuted italic flex flex-col items-center">
                  <Search className="w-12 h-12 opacity-20 mb-3" />
                  No database entries matched "{searchQuery}"
                </div>
              ) : (
                <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 max-h-[500px] overflow-y-auto custom-scrollbar pr-2">
                  {searchResults.map((res: any, idx: number) => renderImageCard(res, idx))}
                </div>
              )}
            </div>
          )}

          {/* Always-visible Full Catalogue Grid */}
          <div className="glass-panel p-6 flex-1 flex flex-col">
            <div className="border-b border-white/10 pb-4 mb-4">
              <h2 className="text-xl font-bold text-white mb-1">Full Catalogue</h2>
              <div className="flex flex-wrap gap-2 mt-4">
                <button 
                  onClick={() => setActiveTab('All')}
                  className={`px-4 py-1.5 rounded-full text-[0.7rem] font-semibold transition-all ${
                    activeTab === 'All' 
                      ? 'bg-primary text-white shadow-[0_2px_10px_rgba(236,72,153,0.3)]' 
                      : 'bg-[#ffffff08] text-textMuted hover:bg-[#ffffff15] hover:text-white'
                  }`}
                >
                  All
                </button>
                {dynamicCategories.map(cat => (
                  <button 
                    key={cat}
                    onClick={() => setActiveTab(cat)}
                    className={`px-4 py-1.5 rounded-full text-[0.7rem] font-semibold transition-all ${
                      activeTab === cat 
                        ? 'bg-primary text-white shadow-[0_2px_10px_rgba(236,72,153,0.3)]' 
                        : 'bg-[#ffffff08] text-textMuted hover:bg-[#ffffff15] hover:text-white'
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar">
              {displayedCatalog.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-textMuted italic py-20">
                  <ImageIcon className="w-16 h-16 mb-4 opacity-20"/>
                  <p className="text-lg">Catalogue is currently empty.</p>
                  <p className="text-sm opacity-60">Run a sorting job to ingest images.</p>
                </div>
              ) : (
              <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {displayedCatalog.map((res: any, idx: number) => renderImageCard(res, idx))}
              </div>
              )}
            </div>
          </div>

        </section>
      </main>

      {/* Pop-up Image Modal */}
      {modalImage && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 md:p-12 bg-black/90 backdrop-blur-md" onClick={() => setModalImage(null)}>
          <div className="bg-panel border border-white/10 rounded-2xl w-full max-w-6xl max-h-[90vh] flex flex-col md:flex-row shadow-2xl overflow-hidden relative" onClick={e => e.stopPropagation()}>
            
            {/* Left side: Full Image */}
            <div className="w-full md:w-2/3 bg-black/50 flex flex-col items-center justify-center relative min-h-[300px] border-b md:border-b-0 md:border-r border-white/5 p-4">
               {!modalImage.placeholder ? (
                 <img src={modalImage.id ? `${API_URL}/api/image?id=${modalImage.id}` : `${API_URL}/api/image?path=${encodeURIComponent(modalImage.new_path || modalImage.original_path || ('/path/' + modalImage.file))}`} className="max-w-full max-h-[85vh] object-contain drop-shadow-2xl rounded" alt={modalImage.file} />
               ) : (
                 <div className="flex flex-col items-center text-textMuted opacity-50"><ImageIcon className="w-20 h-20 mb-4"/><span>Placeholder Image</span></div>
               )}
            </div>

            {/* Right side: Info and Editable Description */}
            <div className="w-full md:w-1/3 p-6 flex flex-col gap-5 overflow-y-auto custom-scrollbar">
               <div>
                 <h3 className="text-xl font-bold text-white break-words mb-3 leading-tight font-sans">{modalImage.file}</h3>
                 <div className="flex flex-wrap items-center gap-2 mb-2">
                   <div className="inline-flex uppercase text-[0.65rem] font-extrabold tracking-widest text-secondary px-3 py-1 rounded-md bg-secondary/10 border border-secondary/20">
                     {modalImage.category}
                   </div>
                   {modalImage.project_tag && modalImage.project_tag.split(',').map((t: string, i: number) => (
                     <div key={i} className="text-primary font-bold text-sm bg-primary/10 px-2 py-0.5 rounded border border-primary/20">#{t.trim()}</div>
                   ))}
                 </div>
                 {modalImage.original_path && <p className="text-xs text-textMuted break-all font-mono opacity-60 mt-2">Source: {modalImage.original_path}</p>}
               </div>
               
               <div className="flex-1 flex flex-col gap-2 relative">
                 <label className="text-white text-sm font-bold flex items-center gap-2"><Pencil className="w-4 h-4 text-primary"/> Edit Description</label>
                 <textarea 
                    value={editDesc}
                    onChange={e => setEditDesc(e.target.value)}
                    className="w-full bg-black/50 border border-primary/30 focus:border-primary focus:ring-1 focus:ring-primary/50 text-textMain outline-none resize-none flex-1 min-h-[250px] rounded-lg p-4 font-medium leading-relaxed custom-scrollbar transition-all"
                 />
               </div>
               
               <div className="flex items-center justify-between pt-2">
                 <button onClick={(e) => { e.stopPropagation(); handleDeleteItem(modalImage.new_path || modalImage.original_path || modalImage.file); setModalImage(null); }} className="p-2 text-textMuted hover:bg-red-500/10 hover:text-red-400 rounded transition-colors group" title="Delete Image">
                    <Trash2 className="w-5 h-5 group-hover:scale-110 transition-transform" />
                 </button>
                 <div className="flex gap-2">
                   <button onClick={() => setModalImage(null)} className="px-5 py-2.5 rounded-lg text-sm text-textMuted hover:text-white bg-white/5 hover:bg-white/10 transition-colors font-semibold">Close</button>
                   <button onClick={() => {
                     handleSaveEdit(modalImage.new_path || modalImage.original_path || modalImage.file);
                   }} className="px-6 py-2.5 bg-gradient-to-r from-primary to-secondary hover:opacity-90 text-white rounded-lg font-bold shadow-lg transition-all text-sm flex items-center gap-2">
                     Save Edits
                   </button>
                 </div>
               </div>
            </div>

            {/* Global Close button */}
            <button onClick={() => setModalImage(null)} className="absolute top-4 right-4 p-2 bg-black/50 text-white/50 hover:text-white rounded-full hover:bg-red-500 transition-all z-10 backdrop-blur-md">
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}
      
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-10 left-1/2 -translate-x-1/2 bg-primary/90 backdrop-blur border border-primary text-white px-6 py-3 rounded-full shadow-[0_0_20px_rgba(217,70,239,0.5)] z-[100] font-bold flex items-center gap-3 transition-all duration-300">
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>
          {toastMessage}
        </div>
      )}

    </div>
  );
}

export default App;
