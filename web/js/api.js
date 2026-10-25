const API={
 token:localStorage.getItem('care_token')||'',
 setToken(t){this.token=t||'';t?localStorage.setItem('care_token',t):localStorage.removeItem('care_token');},
 async raw(path,options={}){
  const headers={Authorization:'Bearer '+this.token,...options.headers};
  const res=await fetch('/api'+path,{...options,headers,cache:'no-store'});
  if(!res.ok){const d=await res.json().catch(()=>({}));if(res.status===401&&path!='/login'){this.setToken('');showLogin();}throw Error(d.error||'请求失败');}
  return res;
 },
 async call(path,{method='GET',body}={}){
  const multipart=body instanceof FormData;
  return (await this.raw(path,{method,headers:multipart?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:multipart?body:JSON.stringify(body)})).json();
 },
 async download(path,name){const blob=await(await this.raw(path)).blob();const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
};
