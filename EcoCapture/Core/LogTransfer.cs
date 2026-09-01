using System.Text;
using System.Text.Json;
using EcoCapture.Transport;

namespace EcoCapture.Core;

public sealed record RemoteLog(string Name,long Size,long Modified,bool Active,int DirectoryOrder);

public sealed class LogTransfer(ConnectionManager connection)
{
    public static List<RemoteLog> OrderedPrimaryLogs(IEnumerable<RemoteLog> files)=>files
        .Where(x=>x.Name.EndsWith(".csv",StringComparison.OrdinalIgnoreCase)&&!x.Name.EndsWith("_can.csv",StringComparison.OrdinalIgnoreCase))
        .OrderBy(x=>x.Active).ThenByDescending(x=>x.DirectoryOrder).ToList();
    public async Task<IReadOnlyList<RemoteLog>> ListAsync(CancellationToken cancellation=default)
    {
        var files=new List<RemoteLog>(); var offset=0;
        while(offset<100000)
        {
            var root=await connection.QueryAsync("listLogs",new { offset },cancellation);
            if(root.TryGetProperty("error",out var error)) throw new IOException(error.GetString());
            foreach(var f in root.GetProperty("files").EnumerateArray())
                files.Add(new(f.GetProperty("name").GetString()??"",f.TryGetProperty("bytes",out var s)?s.GetInt64():0,
                    f.TryGetProperty("modified",out var m)?m.GetInt64():0,f.TryGetProperty("active",out var a)&&a.GetBoolean(),files.Count));
            if(!root.TryGetProperty("next",out var next)||next.ValueKind==JsonValueKind.Null) break;
            offset=next.GetInt32();
        }
        return files;
    }
    public async Task<string> DownloadAsync(RemoteLog file,string directory,IProgress<double>? progress=null,CancellationToken cancellation=default)
    {
        Directory.CreateDirectory(directory); var target=Path.Combine(directory,Path.GetFileName(file.Name)); var part=target+".part";
        await using var output=new FileStream(part,FileMode.Create,FileAccess.Write,FileShare.None,32768,true);
        long offset=0;
        try
        {
            while(true)
            {
                var root=await connection.QueryAsync("readLog",new { name=file.Name,offset },cancellation);
                if(root.TryGetProperty("error",out var error)) throw new IOException(error.GetString());
                var data=root.TryGetProperty("data",out var d)?d.GetString()??"":""; var bytes=Encoding.UTF8.GetBytes(data);
                await output.WriteAsync(bytes,cancellation);
                var next=root.TryGetProperty("next",out var n)?n.GetInt64():offset+bytes.Length;
                if(next<offset||next-offset!=bytes.Length) throw new IOException("SDログの転送位置が一致しません。");
                offset=next; progress?.Report(file.Size>0?Math.Clamp(offset/(double)file.Size,0,1):0);
                if(root.TryGetProperty("eof",out var eof)&&eof.GetBoolean()) break;
                if(bytes.Length==0) throw new IOException("SDログの転送が途中で止まりました。");
            }
            await output.FlushAsync(cancellation); output.Close(); File.Move(part,target,true); progress?.Report(1); return target;
        }
        catch { output.Close(); try{File.Delete(part);}catch{} throw; }
    }
}
