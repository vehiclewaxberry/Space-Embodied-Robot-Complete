import * as THREE from 'three';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {STLLoader} from 'three/addons/loaders/STLLoader.js';
const $=s=>document.querySelector(s), stage=$('#stage'), canvas=$('#canvas');
const renderer=new THREE.WebGLRenderer({canvas,antialias:true,preserveDrawingBuffer:true});
renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.outputColorSpace=THREE.SRGBColorSpace;
renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.23;
const scene=new THREE.Scene();scene.background=new THREE.Color('#e5e9e8');
const camera=new THREE.PerspectiveCamera(36,1,0.005,30);camera.up.set(0,0,1);
const controls=new OrbitControls(camera,canvas);controls.enableDamping=true;controls.dampingFactor=.075;
scene.add(new THREE.HemisphereLight(0xf2f7ff,0x69737c,2.9));
for(const [pos,intensity]of [[[2,-3,4],3.2],[[-3,1,1],1.7],[[0,3,3],2.1]]){const l=new THREE.DirectionalLight(0xffffff,intensity);l.position.set(...pos);scene.add(l)}
const grid=new THREE.GridHelper(3,30,0xa1b2b8,0xc5cfd1);grid.rotation.x=Math.PI/2;grid.position.z=-.14;grid.material.transparent=true;grid.material.opacity=.35;scene.add(grid);
const axes=new THREE.AxesHelper(.15);axes.position.set(-.4,-.5,-.138);scene.add(axes);
const robot=new THREE.Group();scene.add(robot);
const gltf=new GLTFLoader(),stl=new STLLoader(),gltfCache=new Map(),stlCache=new Map();
const groups={structure:['主承载结构','#95adba'],arm:['B601 机械臂','#dba758'],equipment:['舱内设备','#58899e'],mechanisms:['保持与连接机构','#869688'],wings:['太阳翼','#364f72'],envelopes:['功能包络 / 占位','#a980bf']};
const enabled=Object.fromEntries(Object.keys(groups).map(k=>[k,k!=='envelopes']));let data,current='service',objects=[],loaded={},activeSelection=null,internal=false,loadTicket=0;
const title={parking:'开放停放构型',released:'释放构型',service:'服务构型'};
function resize(){const b=stage.getBoundingClientRect();renderer.setSize(b.width,b.height,false);camera.aspect=b.width/b.height;camera.updateProjectionMatrix()};new ResizeObserver(resize).observe(stage);
function frame(){requestAnimationFrame(frame);controls.update();renderer.render(scene,camera)}frame();
function metersMatrix(values){const a=values.slice();a[3]/=1000;a[7]/=1000;a[11]/=1000;return new THREE.Matrix4().set(...a)}
async function cacheGLB(asset){if(!gltfCache.has(asset.sha256))gltfCache.set(asset.sha256,gltf.loadAsync(asset.url));return (await gltfCache.get(asset.sha256)).scene}
async function cacheSTL(asset){if(!stlCache.has(asset.sha256))stlCache.set(asset.sha256,stl.loadAsync(asset.url));return await stlCache.get(asset.sha256)}
async function limited(items,fn,n=5){let i=0;await Promise.all(Array.from({length:Math.min(n,items.length)},async()=>{while(i<items.length){const k=i++;await fn(items[k],k)}}))}
function styleMesh(m,row){const role=row.representation_role, color=row.arm_link?new THREE.Color('#c9b492'):new THREE.Color().setRGB(...row.color.slice(0,3),THREE.LinearSRGBColorSpace);
  if(row.group==='wings')color.set('#263e64');
  m.material=new THREE.MeshStandardMaterial({color,metalness:row.arm_link?.4:.28,roughness:.48,side:THREE.DoubleSide,transparent:role==='FUNCTIONAL_ENVELOPE',opacity:role==='FUNCTIONAL_ENVELOPE'?.2:1,depthWrite:role!=='FUNCTIONAL_ENVELOPE'});m.userData.row=row;}
async function prepare(state){if(loaded[state])return loaded[state];const s=data.states[state],wrappers=[];let done=0;
  await limited(s.occurrences,async row=>{const group=new THREE.Group();group.name=row.id;group.userData.row=row;group.matrixAutoUpdate=false;group.matrix.copy(metersMatrix(row.matrix_mm));group.userData.nominal=group.matrix.clone();
    if(row.arm_link){const geo=await cacheSTL(data.arm_assets[row.arm_link]);const mesh=new THREE.Mesh(geo);styleMesh(mesh,row);group.add(mesh)}
    else{const base=await cacheGLB(s.components[row.component]);const clone=base.clone(true);clone.traverse(m=>{if(m.isMesh)styleMesh(m,row)});group.add(clone)}
    group.updateMatrixWorld(true);group.userData.center=new THREE.Box3().setFromObject(group).getCenter(new THREE.Vector3());wrappers.push(group);done++;$('#loading').textContent=`正在装入${title[state]} · ${done} / ${s.occurrences.length} 个实例`;});
  loaded[state]=wrappers;return wrappers;}
function updateLayers(){const counts={};for(const row of data.states[current].occurrences)counts[row.group]=(counts[row.group]||0)+1;$('#layers').replaceChildren();
  for(const [key,[label,color]]of Object.entries(groups)){const l=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.checked=enabled[key];input.addEventListener('change',()=>{enabled[key]=input.checked;updateVisibility()});const dot=document.createElement('i');dot.className='swatch';dot.style.background=color;const t=document.createElement('span');t.textContent=label;const c=document.createElement('span');c.textContent=counts[key]||0;l.append(input,dot,t,c);$('#layers').append(l)}}
function cover(row){return /^(access_cover_|front_service_cover$|shear_web_-?1$|lower_equipment_deck$|upper_equipment_deck$|wing_-?1_leaf_)/.test(row.id)}
function updateVisibility(){for(const o of objects){o.visible=enabled[o.userData.row.group];o.traverse(m=>{if(m.isMesh&&cover(o.userData.row)){m.material.transparent=internal;m.material.opacity=internal?.12:1;m.material.depthWrite=!internal}})}window.robotReview.visible=objects.filter(o=>o.visible).length}
function fit(reset=false){const box=new THREE.Box3();for(const o of objects)if(o.visible)box.expandByObject(o);const c=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3());const r=Math.max(size.length()/2,.25);const aspectAllowance=Math.max(1,1/camera.aspect);const dist=r/Math.sin(THREE.MathUtils.degToRad(camera.fov/2))*aspectAllowance*.90;const dir=reset?new THREE.Vector3(1.55,-2,1.4).normalize():camera.position.clone().sub(controls.target).normalize();controls.target.copy(c);camera.position.copy(c).addScaledVector(dir.length()?dir:new THREE.Vector3(1,-1,1).normalize(),dist);camera.near=.003;camera.far=Math.max(30,dist*8);camera.updateProjectionMatrix();controls.update()}
function explode(){const value=Number($('#explode').value);for(const o of objects){const row=o.userData.row,c=o.userData.center;let d;
  if(row.group==='arm')d=new THREE.Vector3(.42,0,.48);
  else if(row.group==='wings')d=new THREE.Vector3(0,Math.sign(c.y)*.48,.05);
  else if(row.group==='equipment')d=new THREE.Vector3(Math.sign(c.x)*.24,Math.sign(c.y)*.24,.36);
  else d=new THREE.Vector3(c.x*.65,c.y*.65,c.z*.9);
  o.matrix.copy(o.userData.nominal);o.matrix.elements[12]+=d.x*value;o.matrix.elements[13]+=d.y*value;o.matrix.elements[14]+=d.z*value;o.matrixWorldNeedsUpdate=true;}
  $('#explodeLabel').textContent=value?`示意分解 · ${Math.round(value*100)}% · 不代表安装轨迹`:'原始装配位置 · 0%';window.robotReview.explode=value;}
async function switchState(state){const ticket=++loadTicket;$('#loading').style.display='flex';const values=await prepare(state);if(ticket!==loadTicket)return;current=state;robot.clear();objects=values;for(const o of objects)robot.add(o);$('#explode').value=0;explode();updateLayers();updateVisibility();for(const b of document.querySelectorAll('[data-state]'))b.classList.toggle('active',b.dataset.state===state);
  const s=data.states[state];$('#stateTitle').textContent=title[state]+' / 整机装配';$('#pose').textContent=(state==='parking'?'OPEN_PARKING / 非发射收拢　·　':'')+`B601 关节角 [ ${s.q_deg.join(' · ')} ] °　/　夹指位移 ${s.finger_mm} mm`;
  $('#count').textContent=s.counts.total;$('#armcount').textContent=s.counts.arm;const ledger=s.digital_mass_ledger;$('#countsText').textContent=ledger?`${s.counts.nonarm} 个非臂实例 + ${s.counts.arm} 个臂连杆。${ledger.allocated_instances} 项有数字质量分配，${ledger.unknown_instances} 项 UNKNOWN。分配合计 ${ledger.allocated_mass_kg.toFixed(6)} kg，非实测整机质量。`:`${s.counts.nonarm} 个非臂实例 + ${s.counts.arm} 个臂连杆；${s.counts.unknown_mass} 个实例原始质量字段为 UNKNOWN。`;
  $('#selection').style.display='none';fit(true);$('#loading').style.display='none';window.robotReview={...window.robotReview,state,ready:true,total:s.counts.total,configuration:s.configuration,sourceReceipt:s.receipt};}
function select(row,mesh){if(activeSelection)activeSelection.material.emissive.set(0);activeSelection=mesh;if(mesh)mesh.material.emissive.set('#58351a');$('#selectedName').textContent=row.id;$('#selectedData').replaceChildren();
  const pairs=[['零件号',row.pn],['组件',row.parent_assembly],['接口',row.mount_interface],['几何表示',row.representation_role],['质量来源',row.mass_source],['实例质量',row.mass_kg==null?'UNKNOWN / 未填写':`${row.mass_kg.toFixed(6)} kg`],['工程验证状态',row.qualification_status],['源数据',row.arm_link?'Accepted B601 URDF + STL（米制）；非本轮新建臂 BRep':row.source_revision]];
  for(const [k,v]of pairs){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=k;dd.textContent=v||'未分配';$('#selectedData').append(dt,dd)}$('#selection').style.display='block';window.robotReview.selected=row.id;}
const ray=new THREE.Raycaster(),pointer=new THREE.Vector2();let down;
canvas.addEventListener('pointerdown',e=>down=[e.clientX,e.clientY]);canvas.addEventListener('pointerup',e=>{if(!down||Math.hypot(e.clientX-down[0],e.clientY-down[1])>5)return;const r=canvas.getBoundingClientRect();pointer.set((e.clientX-r.left)/r.width*2-1,-(e.clientY-r.top)/r.height*2+1);ray.setFromCamera(pointer,camera);const hits=ray.intersectObjects(objects.filter(o=>o.visible),true).filter(x=>x.object.isMesh&&x.object.userData.row);if(hits.length)select(hits[0].object.userData.row,hits[0].object)});
$('#close').onclick=()=>$('#selection').style.display='none';$('#fit').onclick=()=>fit();$('#iso').onclick=()=>fit(true);$('#explode').oninput=explode;$('#structureView').onclick=()=>{internal=!internal;$('#structureView').textContent=internal?'恢复外观':'查看内部';updateVisibility()};
for(const b of document.querySelectorAll('[data-state]'))b.onclick=()=>switchState(b.dataset.state).catch(fail);
function fail(e){console.error(e);$('#loading').classList.add('error');$('#loading').style.display='flex';$('#loading').textContent='装配数据未成功装入\n'+e.message;window.robotReview={ready:false,error:e.message};}
window.robotReview={ready:false,representation:'NONARM_CAD_GLB_PLUS_ACCEPTED_ARM_STL',collisionCredit:null};
try{data=await fetch('./scene.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw Error('场景清单读取失败');return r.json()});if(data.development)$('#development').style.display='block';for(const d of data.deliverables||[]){const a=document.createElement('a');a.href=d.url;a.target='_blank';a.textContent=d.label+' ↗';$('#deliverables').append(a)}await switchState('service');if((await fetch('./complete_service_robot.glb',{method:'HEAD'})).ok){const a=document.createElement('a');a.href='./complete_service_robot.glb';a.download='complete_service_robot.glb';a.textContent='完整服务态 GLB（三角网格） ↓';$('#deliverables').prepend(a)}}catch(e){fail(e)}
