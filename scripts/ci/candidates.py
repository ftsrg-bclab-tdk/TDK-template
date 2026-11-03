"""Durable exact release candidates in the same project's immutable GitHub Releases."""
import hashlib
import json
from pathlib import Path
import tempfile
import urllib.parse

from ci.handoff import MAX_BYTES, require, sha_file, extract
from external_inputs.external_inputs import GitHub
from publication_io import RemoteError


def release(http, repository, receipt_digest):
    tag="release-candidates/"+receipt_digest
    try:
        value=http.request("GET","/repos/"+repository+"/releases/tags/"+urllib.parse.quote(tag,safe=""))
    except RemoteError as exc:
        if exc.status==404:return None
        raise
    require(value.get("tag_name")==tag,"Candidate tag mismatch")
    return value


def asset(value,name):
    matches=[a for a in value.get("assets",[]) if a.get("name")==name]
    require(len(matches)==1,"Candidate asset missing or ambiguous")
    return matches[0]


def retain(http, uploads, repository, repository_id, source_sha, receipt_digest, archive, transport, client=None):
    prefix="/repos/"+repository
    require(http.request("GET",prefix).get("id")==repository_id,"Candidate repository mismatch")
    settings=http.request("GET",prefix+"/immutable-releases")
    require(settings.get("enabled") is True or settings.get("enforced_by_owner") is True,"Enable accepted immutable-release setting before durable candidate promotion")
    archive=Path(archive)
    require(transport.get("schema")=="ci-artifact/v1","Expected verified CI transport receipt")
    require(sha_file(archive)==transport["artifact_sha256"],"Candidate bytes differ from verified artifact")
    value=release(http,repository,receipt_digest)
    if value is None:
        # A failed POST is never blindly replayed; the next explicit invocation reads by tag.
        value=http.request("POST",prefix+"/releases",value={"tag_name":"release-candidates/"+receipt_digest,"target_commitish":source_sha,
                           "name":"Reviewed research candidate "+receipt_digest[:12],"draft":True,"prerelease":True,"make_latest":"false"})
    names={"candidate.zip":archive.read_bytes(),"transport.json":(json.dumps(transport,sort_keys=True,indent=2)+"\n").encode()}
    if value.get("draft"):
        for name,data in names.items():
            if any(a.get("name")==name for a in value.get("assets",[])):
                continue
            try:
                uploads.request("POST",prefix+f"/releases/{value['id']}/assets?name="+name,data=data)
            except RemoteError:
                refreshed=http.request("GET",prefix+"/releases/"+str(value["id"]))
                found=asset(refreshed,name)
                require(found.get("digest")=="sha256:"+hashlib.sha256(data).hexdigest(),"Candidate upload outcome is ambiguous")
        value=http.request("GET",prefix+"/releases/"+str(value["id"]))
    client=client or GitHub()
    for name,data in names.items():
        found=asset(value,name)
        require(found.get("size")==len(data),"Candidate asset size mismatch")
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/"asset"
            client.download("repos/"+repository+"/releases/assets/"+str(found["id"]),target,MAX_BYTES)
            require(sha_file(target)==hashlib.sha256(data).hexdigest(),"Candidate download verification failed")
    if value.get("draft"):
        http.request("PATCH",prefix+"/releases/"+str(value["id"]),value={"draft":False,"make_latest":"false"})
        value=http.request("GET",prefix+"/releases/"+str(value["id"]))
    require(value.get("immutable") is True and value.get("draft") is False,"Candidate release is not immutable")
    return {"repository_id":repository_id,"release_id":value["id"],"tag":value["tag_name"],
            "asset_id":asset(value,"candidate.zip")["id"],"artifact_sha256":transport["artifact_sha256"]}


def recover(http,repository,repository_id,receipt_digest,expected,output,client=None):
    require(http.request("GET","/repos/"+repository).get("id")==repository_id,"Recovery repository mismatch")
    value=release(http,repository,receipt_digest)
    require(value and value.get("immutable") is True and value.get("draft") is False,"No durable immutable candidate")
    client=client or GitHub()
    with tempfile.TemporaryDirectory() as directory:
        metadata=Path(directory)/"transport.json"
        client.download("repos/"+repository+"/releases/assets/"+str(asset(value,"transport.json")["id"]),metadata,2*1024*1024)
        transport=json.loads(metadata.read_bytes())
        require(transport.get("schema")=="ci-artifact/v1","Invalid durable transport receipt")
        require(all(transport.get(k)==v for k,v in expected.items()),"Durable producer identity mismatch")
        archive=Path(directory)/"candidate.zip"
        client.download("repos/"+repository+"/releases/assets/"+str(asset(value,"candidate.zip")["id"]),archive,MAX_BYTES)
        require(sha_file(archive)==expected["artifact_sha256"],"Durable candidate digest mismatch")
        extract(archive,Path(output))
    return transport,{"repository_id":repository_id,"release_id":value["id"],"tag":value["tag_name"],
                       "asset_id":asset(value,"candidate.zip")["id"],"artifact_sha256":expected["artifact_sha256"]}
