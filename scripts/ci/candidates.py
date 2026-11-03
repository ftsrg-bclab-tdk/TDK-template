"""Durable exact release candidates in the same project's immutable GitHub Releases."""
import hashlib
import json
from pathlib import Path
import tempfile

from ci.handoff import MAX_BYTES, require, sha_file, extract
from external_inputs.external_inputs import GitHub
from publication_io import RemoteError


def release(http, repository, receipt_digest):
    tag="release-candidates/"+receipt_digest
    # The tag endpoint only returns published releases. List drafts before creating
    # anything so a lost draft-create response does not produce another release.
    matches=[]
    for page in range(1,21):
        values=http.request("GET",f"/repos/{repository}/releases?per_page=100&page={page}")
        require(isinstance(values,list),"Invalid release listing")
        matches.extend(value for value in values if value.get("tag_name")==tag)
        if len(values)<100:
            break
    else:
        raise ValueError("Release listing incomplete; reconcile before retry")
    require(len(matches)<=1,"Candidate tag is ambiguous; reconcile before retry")
    return matches[0] if matches else None


def asset(value,name):
    matches=[a for a in value.get("assets",[]) if a.get("name")==name]
    require(len(matches)==1,"Candidate asset missing or ambiguous")
    return matches[0]


def retain(http, uploads, repository, repository_id, source_sha, receipt_digest, archive, transport, client=None):
    prefix="/repos/"+repository
    require(http.request("GET",prefix).get("id")==repository_id,"Candidate repository mismatch")
    # GITHUB_TOKEN cannot request Administration:read for the settings endpoint.
    # An owner enables immutability during setup. Verify the actual published
    # release below before returning any durable receipt or calling Zenodo.
    archive=Path(archive)
    require(transport.get("schema")=="ci-artifact/v1","Expected verified CI transport receipt")
    require(sha_file(archive)==transport["artifact_sha256"],"Candidate bytes differ from verified artifact")
    value=release(http,repository,receipt_digest)
    if value is None:
        # A failed POST is reconciled against the draft-inclusive listing next time.
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
    require(value.get("immutable") is True and value.get("draft") is False,"Candidate release is not immutable; owner must enable immutable releases and reconcile this candidate before retry")
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
