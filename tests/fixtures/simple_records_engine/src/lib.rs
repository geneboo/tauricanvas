use serde::{Deserialize,Serialize};
#[derive(Clone,Serialize,Deserialize)] pub struct Record{pub id:u64,pub name:String,pub enabled:bool}
#[derive(Clone,Serialize,Deserialize)] pub struct SaveRecordRequest{pub id:Option<u64>,pub name:String,pub enabled:bool}
#[derive(Debug)] pub struct EngineError(pub String);
pub async fn list_records()->Result<Vec<Record>,EngineError>{Ok(vec![Record{id:1,name:"Alpha".into(),enabled:true}])}
pub async fn get_record(id:u64)->Result<Option<Record>,EngineError>{Ok(list_records().await?.into_iter().find(|x|x.id==id))}
pub async fn save_record(r:SaveRecordRequest)->Result<Record,EngineError>{Ok(Record{id:r.id.unwrap_or(2),name:r.name,enabled:r.enabled})}
pub unsafe fn raw_pointer(p:*const u8)->u8{*p}
