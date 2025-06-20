import UserAgent from 'user-agents';

export function makeClientHints(ua: UserAgent): Record<string, string> {
  const uastr = ua.toString();
  const lo = uastr.toLowerCase();
  const headers: Record<string,string> = {};

  // platform
  let platform = 'Unknown';
  if (lo.includes('android')) platform = 'Android';
  else if (lo.includes('iphone') || lo.includes('ipad')) platform = 'iOS';
  else if (lo.includes('win')) platform = 'Windows';
  else if (lo.includes('macintosh')) platform = 'macOS';
  else if (lo.includes('linux')) platform = 'Linux';
  headers['Sec-CH-UA-Platform'] = `"${platform}"`;

  // mobile
  const isMobile = /Mobi|Android|iPhone/i.test(uastr);
  headers['Sec-CH-UA-Mobile'] = isMobile ? '?1' : '?0';

  // brands
  let major: string | undefined;
  if (uastr.includes('Edg/')) {
      major = (uastr.match(/Edg\/(\d+)/) || [])[1];
      if (major) headers['Sec-CH-UA'] = `"Not_A Brand";v="8", "Chromium";v="${major}", "Microsoft Edge";v="${major}"`;
  } else if (uastr.includes('Chrome/')) {
      major = (uastr.match(/Chrome\/(\d+)/) || [])[1];
      if (major) headers['Sec-CH-UA'] = `"Not_A Brand";v="8", "Chromium";v="${major}", "Google Chrome";v="${major}"`;
  } else if (uastr.includes('Firefox/')) {
      major = (uastr.match(/Firefox\/(\d+)/) || [])[1];
      if (major) headers['Sec-CH-UA'] = `"Firefox";v="${major}"`;
  }
  return headers;
}

export function defaultHeaders(): Record<string,string> {
  return {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/*,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Cache-Control': 'max-age=0',
    'DNT': '1',
    'Sec-GPC': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1'
  };
}
