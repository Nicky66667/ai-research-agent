import os
import boto3 # aws tool bag
import botocore.exceptions
from botocore.exceptions import ClientError

BUCKET_NAME = os.environ["S3_BUCKET_NAME"]
_s3 = boto3.client("s3", region_name = os.environ.get("AWS_REGION","us-east-1"))

def	pdf_key(arxiv_id:	str)	->	str:
	"""统一生成	S3	里的存储路径（key）"""
	safe_id	=	arxiv_id.replace("arxiv:",	"").replace("/",	"_")
	return	f"papers/{safe_id}.pdf"

def	exists_in_s3(arxiv_id:	str)	->	bool:
	"""检查这篇论文是否已经缓存在	S3"""
	try:
		_s3.head_object(Bucket=BUCKET_NAME,	Key=pdf_key(arxiv_id))
		return	True
	except	ClientError	as	e:
		if	e.response["Error"]["Code"]	==	"404":
			return	False
		raise		#	其他错误（比如权限问题）不要吞掉，抛出来方便排查

def	upload_pdf(arxiv_id:	str,	pdf_bytes:	bytes)	->	str:
	"""把	PDF	二进制内容上传到	S3，返回	S3	key"""
	key	=	pdf_key(arxiv_id)
	_s3.put_object(Bucket=BUCKET_NAME,	Key=key,	Body=pdf_bytes,	ContentType="application/pdf")
	return	key

def	download_pdf(arxiv_id:	str)	->	bytes:
	"""从	S3	下载	PDF	二进制内容"""
	response	=	_s3.get_object(Bucket=BUCKET_NAME,	Key=pdf_key(arxiv_id))
	return	response["Body"].read()