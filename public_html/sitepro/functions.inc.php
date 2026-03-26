<?php

use PHPMailer\PHPMailer\PHPMailer;

function getRequestUri($baseUrl) {
	$nh = preg_replace('#/\./#', '/', $baseUrl);
	$nh = preg_replace('#^http[s]*://[^/]+/#i', '/', $nh);
	$nh = preg_replace('#/[^/]+/\.\./#i', '/', $nh);
	if (isset($_SERVER['HTTP_X_REQUEST_URI'])) {
		$ru = trim(urldecode($_SERVER['HTTP_X_REQUEST_URI']));
	} else if (isset($_SERVER['REQUEST_URI'])) {
		$ru = trim(urldecode($_SERVER['REQUEST_URI']));
	} else {
		$ru = '/';
	}
	
	// Note: fix issue with MS IIS server.
	if ($ru == '/index.php' && is_null(_get('route'))) $ru = '/';
	$ru = preg_replace('#'.preg_quote($nh).'#i', '', $ru, 1);
	list($ru) = explode('?', $ru, 2);
	return $ru;
}

function parse_uri(SiteInfo $siteInfo, SiteRequestInfo $requestInfo) {
	$ru = $requestInfo->requestUri;
	if (!is_null(_get('route'))) {
		$ru = trim(_get('route'));
	}
	$ru = preg_split('#[\ \t]*[/]+[\ \t]*#i', $ru, -1, PREG_SPLIT_NO_EMPTY);
	$ru = array_map('trim', $ru);
	
	$cusr = null;
	if (strpos(ini_get('disable_functions'), 'get_current_user') === false) {
		$cusr = get_current_user();
	}
	if ($cusr && !empty($ru) && ($ru[0] == ('~'.$cusr) || $ru[0] == ($cusr.'~'))) {
		array_shift($ru);
	}
	
	if (isset($ru[0]) && preg_match('#^[a-z]{2}-[A-Z]{2}$#', $ru[0])) {
		array_shift($ru);
	}
	
	if (!count($ru)) {
		foreach ($siteInfo->pages as $idx => $pi) {
			if ($siteInfo->homePageId == $pi['id']) return array($idx, $siteInfo->defLang, array(), null);
		}
		return array($siteInfo->homePageId, $siteInfo->defLang, array(), null);
	}
	
	$show_comments = false;
	
	if (false) {
		if ($ru[0] == 'news') {
			$pageIdx = getPageIndexById(isset($ru[1]) ? intval($ru[1]) : null, $siteInfo);
			$route = array_shift($ru);
			return array($pageIdx, $siteInfo->defLang, $ru, $route);
		}
		else if ($ru[0] == 'blog') {
			$pageIdx = getPageIndexById(isset($ru[1]) ? intval($ru[1]) : null, $siteInfo);
			$route = array_shift($ru);
			return array($pageIdx, $siteInfo->defLang, $ru, $route);
		}
	}
	
	$defLang = ($siteInfo->defLang ? $siteInfo->defLang : null);
	$lang = $defLang; $langArg = null;
	if ($siteInfo->langs && is_array($siteInfo->langs) && isset($siteInfo->langs[$ru[0]])) {
		$langArg = array_shift($ru);
		$lang = $langArg;
	}
	$ru_ = array_shift($ru);
	
	if (!$ru_) {
		foreach ($siteInfo->pages as $idx => $pi) {
			if ($siteInfo->homePageId == $pi['id']) {
				if ($langArg && $langArg == $defLang) {
					header('Location: '.getBaseUrl() . getPageUri($pi['id'], $defLang, $siteInfo), true, 301);
					exit();
				}
				return array($idx, $lang, $ru, null);
			}
		}
		return array($siteInfo->homePageId, $lang, $ru, null);
	}
	
	$ruBak = array_merge(array($ru_), $ru); $ruBakOther = array();
	while (!empty($ruBak)) {
		$ru_ = implode('/', $ruBak);
		foreach ($siteInfo->pages as $idx => $pi) {
			if (is_array($pi['alias'])) {
				if ($lang && isset($pi['alias'][$lang]) && $ru_ == $pi['alias'][$lang]) {
					if ($langArg && $langArg == $defLang) {
						header('Location: '.getBaseUrl() . getPageUri($pi['id'], $defLang, $siteInfo), true, 301);
						exit();
					}
					return array($idx, $lang, $ruBakOther, $ru_);
				}
			} else if ($ru_ == $pi['alias']) {
				return array($idx, $lang, $ruBakOther, $ru_);
			}
		}
		array_unshift($ruBakOther, array_pop($ruBak));
	}
	
	$hasMbstring = function_exists('mb_strtolower');
	foreach ($siteInfo->pages as $idx => $pi) {
		if (is_array($pi['alias'])) {
			if ($lang && isset($pi['alias'][$lang]) && ($lnAlias = $pi['alias'][$lang])) {
				if ($hasMbstring && mb_strtolower($ru_) == mb_strtolower($lnAlias) || !$hasMbstring && strtolower($ru_) == strtolower($lnAlias)) {
					header('Location: '.getBaseUrl() . getPageUri($pi['id'], $lang, $siteInfo), true, 301);
					exit();
				}
			}
		} else {
			if ($hasMbstring && mb_strtolower($ru_) == mb_strtolower($pi['alias']) || !$hasMbstring && strtolower($ru_) == strtolower($pi['alias'])) {
				header('Location: '.getBaseUrl() . getPageUri($pi['id'], $lang, $siteInfo), true, 301);
				exit();
			}
		}
	}
	
	foreach ($siteInfo->pages as $idx => $pi) {
		if ($ru_ == $pi['id']) {
			header('Location: '.getBaseUrl() . getPageUri($pi['id'], $lang, $siteInfo), true, 301);
			exit();
		}
	}
	
	return array(-1, $lang, array_merge(array($ru_), $ru), null);
}

function handleTrailingSlashRedirect(SiteInfo $siteInfo, SiteRequestInfo $requestInfo, array $disableNoSlashUrls) {
	if (!$requestInfo->page) return;
	$ru = $requestInfo->requestUri;
	if ($ru && isset($_SERVER['REQUEST_METHOD']) && $_SERVER['REQUEST_METHOD'] == 'GET' && !file_get_contents('php://input')) {
		$qs = getQueryString();
		$hasTrailingSlash = (substr(ltrim($ru, '/'), -1) == '/');

		$route = explode('/', ($requestInfo->route ? $requestInfo->route : ''));
		$disableNoSlashes = false;
		if (count($route) == 1 && in_array(strtolower($route[0]), $disableNoSlashUrls)) {
			$disableNoSlashes = true;
		}

		if ($siteInfo->useTrailingSlashes && !$hasTrailingSlash) {
			header('Location: '.getBaseUrl() . $ru.'/'.($qs ? '?'.$qs : ''), true, 301);
			exit();
		} else if (!$siteInfo->useTrailingSlashes && $hasTrailingSlash && !$disableNoSlashes) {
			header('Location: '.getBaseUrl() . rtrim($ru, '/').($qs ? '?'.$qs : ''), true, 301);
			exit();
		}
	}
}

/** @param string $pageId */
function getPageIndexById($pageId, SiteInfo $siteInfo) {
	foreach ($siteInfo->pages as $id => $pi) {
		if ($pageId == $pi['id']) return $id;
	}
	return null;
}

function getQueryString() {
	$qs = isset($_SERVER['QUERY_STRING']) ? $_SERVER['QUERY_STRING'] : '';
	if (!$qs) {
		$parts = explode('?', (isset($_SERVER['REQUEST_URI']) ? $_SERVER['REQUEST_URI'] : ''), 2);
		if (isset($parts[1]) && $parts[1]) {
			$qs = $parts[1];
		}
	}
	return $qs;
}

function getCurrUrl($cutQuery = false, $forceProto = null) {
	$currIsHttps = isHttps();
	$useHttps = $forceProto ? ($forceProto == 'https') : $currIsHttps;
	list($host) = explode(':', (isset($_SERVER['HTTP_HOST']) ? $_SERVER['HTTP_HOST'] : 'localhost'), 2);
	$url = ($useHttps ? 'https' : 'http').'://'.$host;
	$port = getServerPort();
	if ($currIsHttps != $useHttps && $useHttps && SiteModule::$siteInfo->port) {
		$port = SiteModule::$siteInfo->port;
	}
	if ($port && $port != 80 && ($currIsHttps && $port != 443 || !$currIsHttps)) {
		$url .= ':'.$port;
	}
	$url .= '/';
	list($uri) = explode('?', (isset($_SERVER['REQUEST_URI']) ? $_SERVER['REQUEST_URI'] : ''), 2);
	if (!$cutQuery) {
		$qs = getQueryString();
		$uri .= $qs ? '?'.$qs : '';
	}
	if (isset($_SERVER['REQUEST_METHOD']) && $_SERVER['REQUEST_METHOD'] == 'GET') {
		$hasTrailingSlash = (substr(ltrim($uri, '/'), -1) == '/');
		if ($uri != '/' && $hasTrailingSlash && !SiteModule::$siteInfo->useTrailingSlashes) {
			$uri = rtrim($uri, '/');
		} else if (!$hasTrailingSlash && SiteModule::$siteInfo->useTrailingSlashes) {
			$uri = $uri.'/';
		}
	}
	return $url . ltrim($uri, '/');
}

function generateCanonicalUrl($sitemapUrls) {
	$canonical = getCurrentCanonicalUrl($sitemapUrls);
	if ($canonical) {
		return '<link rel="canonical" href="'.htmlspecialchars($canonical).'" />';
	}

	return '';
}

function getCurrentCanonicalUrl($sitemapUrls) {
	$result = '';

	$url = getCurrUrl(true);

	$parsedUrl = parse_url($url);
	$components = urldecode(isset($parsedUrl['path']) ? $parsedUrl['path'] : $url);
	$components = array_filter(explode('/', $components), function($p) { return trim($p) != ''; });
	if (empty($components)) $components[] = '';

	$sitemapUrls = array_flip(array_map(function ($url) {
		$parsedUrl = parse_url($url);
		return isset($parsedUrl['path']) ? $parsedUrl['path'] : $url;
	}, $sitemapUrls));

	$lim = count($components);
	for ($i = 0; $i < $lim; $i++) {
		$componentsString = implode('/', $components);
		if ($componentsString) {
			$item = '/' . $componentsString . (SiteModule::$siteInfo->useTrailingSlashes ? '/' : '');
		} else {
			$item = '/';
		}

		if (isset($sitemapUrls[$item])) {
			$isHttps = isHttps();
			list($host) = explode(':', (isset($_SERVER['HTTP_HOST']) ? $_SERVER['HTTP_HOST'] : 'localhost'), 2);
			$host = ($isHttps ? 'https' : 'http').'://'.$host;
			$result = $host . $item;
			break;
		}

		$components = array_slice($components, 0, count($components) - 1);
	}

	return $result;
}

function getOrigin() {
	$baseUrl = getBaseUrl();
	$parts = parse_url($baseUrl);
	return $parts['scheme'].'://'.$parts['host'].
			((isset($parts['port']) && $parts['port']) ? ':'.$parts['port'] : '').'/';
			
}

function getBaseUrl() {
	if (SiteModule::$siteInfo->baseUrl != '/') {
		$url = SiteModule::$siteInfo->baseUrl;
	} else {
		$isHttps = isHttps();
		list($host) = explode(':', (isset($_SERVER['HTTP_HOST']) ? $_SERVER['HTTP_HOST'] : 'localhost'), 2);
		$url = ($isHttps ? 'https' : 'http').'://'.$host;
		$port = SiteModule::$siteInfo->port;
		if (!$port && ($serverPort = getServerPort())) {
			$port = $serverPort;
		}
		if ($port && $port != 443 && $port != 80) {
			$url .= ':'.$port;
		}
		$url .= '/';
	}
	if (!SiteModule::$siteInfo->modRewrite && SiteModule::$siteInfo->pathPrefix) {
		$url .= SiteModule::$siteInfo->pathPrefix.'/';
	}
	return $url;
}

function randomHash($len = 17, $onlyDigits = false) {
	$str = ''; $chars = '0123456789'.($onlyDigits ? '' : 'ABCDEFGHJKLMNOPQRSTUVWXZ');
	for ($i = 0; $i < $len; $i++) {
		$min = ($onlyDigits && $i == 0) ? 1 : 0; $max = strlen($chars) - 1;
		$str .= $chars[rand($min, $max)];
	}
	return $str;
}

function getPreferredLang() {
	return SiteModule::getPreferredLang();
}

function getPageUri($pageId, $lang, SiteInfo $siteInfo) {
	$uri = '';
	$isAnchor = false;
	foreach ($siteInfo->pages as $pi) {
		if ($pi['id'] != $pageId) continue;
		if (is_array($pi['alias'])) {
			$useLang = null;
			if ($lang && isset($pi['alias'][$lang])) {
				$useLang = $lang;
			} else if ($siteInfo->defLang && isset($pi['alias'][$siteInfo->defLang])) {
				$useLang = $siteInfo->defLang;
			}
			if ($useLang) {
				$isAnchor = (strpos($pi['alias'][$useLang], '#') !== false);
				$hasRoutePfx = (preg_match('#^\.\.\/\?route=#', $pi['alias'][$useLang]));
				$uri = '';
				if (!$siteInfo->modRewrite && !$hasRoutePfx)
					$uri .= '../?route=';
				if (!$isAnchor && $useLang != $siteInfo->defLang)
					$uri .= $useLang.'/';
				$uri .= $pi['alias'][$useLang];
				$uri = trim($uri, '/');
				if (!$isAnchor && $uri) {
					$uri .= '/';
				}
				break;
			}
		} else {
			$uri = (!$siteInfo->modRewrite && !preg_match('#^\.\.\/\?route=#', $pi['alias']) ? '../?route=' : '').
					$pi['alias'] . ($pi['alias'] ? '/' : '');
		}
	}
	if (isset($_SERVER['REQUEST_METHOD']) && $_SERVER['REQUEST_METHOD'] == 'GET') {
		$hasTrailingSlash = (substr(ltrim($uri, '/'), -1) == '/');
		if ($uri != '/' && $hasTrailingSlash && !SiteModule::$siteInfo->useTrailingSlashes) {
			$uri = rtrim($uri, '/');
		} else if (!$hasTrailingSlash && SiteModule::$siteInfo->useTrailingSlashes && !$isAnchor) {
			$uri = $uri.'/';
		}
	}
	return ltrim($uri, '/');
}

function handleComments($pageId, SiteInfo $siteInfo) {
	$post = $_POST;
	if (isset($post['postComment'])) {
		// message field is used as "Honney Pot" trap
		if ($pageId && isset($post['message']) && !$post['message']) {
			$file = dirname(__FILE__).'/'.$pageId.'.comments.dat';
			$dataStr = is_file($file) ? file_get_contents($file) : null;
			$data = $dataStr ? json_decode($dataStr) : array();
			if (trim($post['text'])) {
				$data[] = array(
					'date' => date('Y-m-d'),
					'time' => date('H:i'),
					'user' => ($post['name'] ? $post['name'] : 'anonymous'),
					'text' => substr($post['text'], 0, 200)
				);
				file_put_contents($file, json_encode($data));
			}
		}
		list($ruA) = explode('?', (isset($_SERVER['REQUEST_URI']) ? $_SERVER['REQUEST_URI'] : ''));
		list($ru) = explode('#', $ruA);
		header('Location: '.$ru.'#wb_comment_box');
		exit();
	}
}

function renderComments($pageId = null) {
	$comments = array();
	$dataFile = dirname(__FILE__).'/'.$pageId.'.comments.dat';
	$dataStr = is_file($dataFile) ? file_get_contents($dataFile) : null;
	$data = $dataStr ? json_decode($dataStr) : null;
	if ($data && is_array($data)) {
		$comments = array_reverse($data);
	}
	include dirname(__FILE__).'/comments.tpl.php';
}

/**
 * Parse multi-lingual value.
 * @param mixed $value
 * @param string $ln
 * @param string $default
 * @return string
 */
function tr_($value, $ln = '', $default = '') {
	if (!$ln) $ln = SiteModule::$lang;
	if (!$ln) $ln = SiteModule::$siteInfo->defLang;
	if (!$ln) $ln = SiteModule::$siteInfo->baseLang;
	if (is_array($value)) {
		if ($ln && isset($value[$ln]) && $value[$ln] !== '') {
			return $value[$ln];
		} else {
			foreach ($value as $v) { return $v; }
		}
	} else if (is_object($value)) {
		if ($ln && isset($value->{$ln}) && $value->{$ln} !== '') {
			return $value->{$ln};
		} else {
			foreach ($value as $v) { return $v; }
		}
	}
	return ($value) ? $value : $default;
}

/**
 * @param string|array|object $value
 * @return string[]
 */
function trLangs_($value) {
	$result = array();
	if (is_array($value)) {
		$langs = array_keys($value);
	} else if (is_object($value)) {
		$langs = array_keys(get_object_vars($value));
	} else {
		$langs = array();
	}
	foreach ($langs as $ln) {
		if ($ln) $result[$ln] = 1;
	}
	return array_keys($result);
}

function popSessionOrGlobalVar($key) {
	if (!$key) return null;
	if (session_id() && isset($_SESSION[$key])) {
		$var = $_SESSION[$key];
		unset($_SESSION[$key]);
		return $var;
	} else {
		global $$key;
		if ($$key) return $$key;
	}
	return null;
}

function sessionOrGlobalVar($key) {
	if (!$key) return null;
	if (session_id() && isset($_SESSION[$key])) {
		return $_SESSION[$key];
	} else {
		global $$key;
		if ($$key) return $$key;
	}
	return null;
}

function getServerPort() {
	$port = (isset($_SERVER['HTTP_X_FORWARDED_PORT']) && is_numeric($_SERVER['HTTP_X_FORWARDED_PORT']))
		? intval($_SERVER['HTTP_X_FORWARDED_PORT'])
		: 0;
	if (!$port && isset($_SERVER['SERVER_PORT']) && is_numeric($_SERVER['SERVER_PORT'])) {
		$port = intval($_SERVER['SERVER_PORT']);
	}
	return $port;
}

function getRemoteAddr() {
	$remoteAddr = (isset($_SERVER['REMOTE_ADDR']) && is_string($_SERVER['REMOTE_ADDR'])) ? $_SERVER['REMOTE_ADDR'] : '';
	if ($remoteAddr != '127.0.0.1' && $remoteAddr != '::1') return $remoteAddr;
	
	$forwarded = (isset($_SERVER['HTTP_X_FORWARDED_FOR']) && is_string($_SERVER['HTTP_X_FORWARDED_FOR']))
		? $_SERVER['HTTP_X_FORWARDED_FOR']
		: '';
	$ips = explode(',', trim($forwarded, " \t\r\n\0\x0B,"));
	return ($ip = trim($ips[count($ips) - 1])) ? $ip : $remoteAddr;
}

function isHttps() {
	return (isset($_SERVER['HTTP_X_FORWARDED_PROTO']) && strpos($_SERVER['HTTP_X_FORWARDED_PROTO'], 'https') !== false
			|| isset($_SERVER['HTTP_X_FORWARDED_PROTOCOL']) && $_SERVER['HTTP_X_FORWARDED_PROTOCOL'] == 'https'
			|| isset($_SERVER['HTTP_X_REMOTE_PROTO']) && $_SERVER['HTTP_X_REMOTE_PROTO'] == 'https'
			|| isset($_SERVER['HTTPS']) && ($_SERVER['HTTPS'] == 'on' || $_SERVER['HTTPS'] == 1)
			|| isset($_SERVER['HTTP_X_HTTPS']) && ($_SERVER['HTTP_X_HTTPS'] == 'on' || $_SERVER['HTTP_X_HTTPS'] == 1)
			|| isset($_SERVER['SERVER_PORT']) && $_SERVER['SERVER_PORT'] == 443
			|| isset($_SERVER['REQUEST_SCHEME']) && $_SERVER['REQUEST_SCHEME'] == 'https'
			|| isset($_SERVER['SERVER_PROTOCOL']) && preg_match('#https#i', $_SERVER['SERVER_PROTOCOL'])
			|| isset($_SERVER['HTTP_CF_VISITOR']) && preg_match('#https#i', $_SERVER['HTTP_CF_VISITOR'])
			|| isset($_SERVER['HTTP_SSL']) && $_SERVER['HTTP_SSL']);
}

function handleForms($page_id, SiteInfo $siteInfo) {
	global $post;
	$forms = $siteInfo->forms;
	// check to ensure that all parameters are ok as well as protect from bots
	// and hackers
	$post = $_POST;
	if (!isset($post['wb_form_id'])
		|| $post['message'] !== ''
		|| !isset($forms)
		|| !is_array($forms)
		|| !isset($page_id)
		|| !(isset($forms[$page_id]) || isset($forms['blog']) || isset($forms['store']))
		|| !(isset($forms[$page_id][$post['wb_form_id']]) || isset($forms['blog'][$post['wb_form_id']]) || isset($forms['store'][$post['wb_form_id']]))
		|| !(isset($forms[$page_id][$post['wb_form_id']]['fields']) || isset($forms['blog'][$post['wb_form_id']]['fields']) || isset($forms['store'][$post['wb_form_id']]['fields']))
		|| isset($post['forms'])
		|| !is_null(_get('forms'))
	) return;

	$secure_token = isset($post['secure_token']) ? $post['secure_token'] : '';
	$secure_token = explode(':', $secure_token);
	$secure_token_id = isset($secure_token[0]) ? $secure_token[0] : '';
	$secure_token = isset($secure_token[1]) ? $secure_token[1] : '';
	unset($post['secure_token']);
	if (session_id() && $secure_token_id && isset($_SESSION['wb_form_secure_token_' . $secure_token_id]) && $_SESSION['wb_form_secure_token_' . $secure_token_id] === $secure_token) {
		$form = isset($forms[$page_id][$post['wb_form_id']])
			? $forms[$page_id][$post['wb_form_id']] : (isset($forms['store'][$post['wb_form_id']])
				? $forms['store'][$post['wb_form_id']] : (isset($forms['blog'][$post['wb_form_id']])
					? $forms['blog'][$post['wb_form_id']] : null));
		if (!$form) return;

		$formSendType = isset($form['formSendType']) ? $form['formSendType'] : 'email';
		$apiPostUrl = (isset($form['postUrl']) && $form['postUrl']) ? $form['postUrl'] : null;
		$webhookUrl = (isset($form['webhookUrl']) && $form['webhookUrl']) ? $form['webhookUrl'] : null;
		$brandId = (isset($form['brandId']) && $form['brandId']) ? $form['brandId'] : null;
		$telegramApiToken = (isset($form['telegramApiToken']) && $form['telegramApiToken']) ? trim($form['telegramApiToken']) : null;
		$telegramChatId = (isset($form['telegramChatId']) && $form['telegramChatId']) ? trim($form['telegramChatId']) : null;

		try {
			global $wb_form_send_state, $wb_form_send_success, $wb_form_reaccept_cookie, $wb_form_id, $formErrors, $wb_form_popup_mode, $wb_target_origin;

			$formErrors = new stdClass();
			$wb_form_reaccept_cookie = false;
			$wb_form_send_state = false;
			$wb_form_send_success = false;
			$wb_form_id = $post['wb_form_id'];
			$wb_form_popup_mode = (isset($post['wb_popup_mode']) && $post['wb_popup_mode'] == 1);
			$wb_target_origin = getOrigin();

			$wb_form_sending_failed = SiteModule::__('Form sending failed');

			if (isset($form['recVersion']) && ($form['recVersion'] == 'v2' || $form['recVersion'] == 'v3')) {
				if (isset($form['recSiteKey']) && $form['recSiteKey'] && isset($form['recSecretKey']) && $form['recSecretKey']) {
					if (isset($post['cookieDontAllow']) && $post['cookieDontAllow'] == '1') {
						$wb_form_reaccept_cookie = true;
						throw new ErrorException(SiteModule::__('Please accept cookie consent to submit the form'));
					}
					// reCAPTCHA is enabled
					$recResp = (isset($post['g-recaptcha-response']) ? $post['g-recaptcha-response'] : '');
					$remoteAddr = getRemoteAddr();
					$respStr = $recResp ? _http_get('https://www.google.com/recaptcha/api/siteverify', array(
						'secret' => $form['recSecretKey'],
						'response' => $recResp,
						'remoteip' => $remoteAddr ? $remoteAddr : null
					)) : null;
					$resp = $respStr ? json_decode($respStr) : null;
					if (!$resp || !isset($resp->success) || !$resp->success) {
						throw new ErrorException(SiteModule::__('Form was not sent, are you a robot?'));
					}
				}
			} elseif (isset($form['recVersion']) && $form['recVersion'] == 'yandex') {
				if (isset($form['recSiteKey']) && $form['recSiteKey']) {
					$recResp = (isset($post['smart-token']) ? $post['smart-token'] : '');
					$remoteAddr = getRemoteAddr();

					$ch = curl_init("https://smartcaptcha.yandexcloud.net/validate");
					$args = [
						"secret" => $form['recSecretKey'],
						"token" => $recResp,
						"ip" => $remoteAddr ? $remoteAddr : null,
					];
					curl_setopt($ch, CURLOPT_TIMEOUT, 1);
					curl_setopt($ch, CURLOPT_POST, true);
					curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($args));
					curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

					$server_output = curl_exec($ch);
					$httpcode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
					$errcode = curl_errno($ch);
					$errmsg = curl_error($ch);
					curl_close($ch);

					if ($httpcode !== 200) {
						if ($errcode > 0) {
							error_log("[Form captcha error]: hcpatcha error: curl error ($errcode)" . ($errmsg ? ": $errmsg" : ''));
						} else {
							error_log("[Form captcha error]: hcaptcha error: http code ($httpcode)" . ($server_output ? ": $server_output" : ''));
						}
						throw new ErrorException(SiteModule::__('Form was not sent, are you a robot?') . ' (2)');
					}

					$resp = json_decode($server_output);
					if ($resp->status !== "ok") {
						throw new ErrorException(SiteModule::__('Form was not sent, are you a robot?'));
					}
				}
			} elseif (isset($form['recVersion']) && $form['recVersion'] == 'hcaptcha') {
				if (isset($form['recSiteKey']) && $form['recSiteKey']) {
					$recResp = (isset($post['h-captcha-response']) ? $post['h-captcha-response'] : '');
					$remoteAddr = getRemoteAddr();

					$ch = curl_init("https://api.hcaptcha.com/siteverify");
					$args = [
						"secret" => $form['recSecretKey'],
						"response" => $recResp,
						"remoteip" => $remoteAddr ? $remoteAddr : null,
					];
					curl_setopt($ch, CURLOPT_TIMEOUT, 1);
					curl_setopt($ch, CURLOPT_POST, true);
					curl_setopt($ch, CURLOPT_POSTFIELDS, http_build_query($args));
					curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

					$server_output = curl_exec($ch);
					$httpcode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
					$errcode = curl_errno($ch);
					$errmsg = curl_error($ch);
					curl_close($ch);

					if ($httpcode !== 200) {
						if ($errcode > 0) {
							error_log("[Form captcha error]: hcpatcha error: curl error ($errcode)" . ($errmsg ? ": $errmsg" : ''));
						} else {
							error_log("[Form captcha error]: hcaptcha error: http code ($httpcode)" . ($server_output ? ": $server_output" : ''));
						}
						throw new ErrorException(SiteModule::__('Form was not sent, are you a robot?') . ' (2)');
					}

					$resp = json_decode($server_output);
					if ($resp->success !== true && $resp->success !== 'true') {
						throw new ErrorException(SiteModule::__('Form was not sent, are you a robot?'));
					}
				}
			}

			$attachmentsDir = dirname(__FILE__) . DIRECTORY_SEPARATOR . "forms_attachments";

			$fields = $form['fields'];
			if (isset($form['useGclidCapture']) && $form['useGclidCapture'] && !is_null(_get('gclid'))) {
				$idx = count($fields);
				$fields[$idx] = [
					"fidx" => $idx,
					"name" => "gclid",
					"default" => htmlspecialchars(_get('gclid')),
					"type" => "hidden",
					"required" => false,
					"enabled" => true,
					"settings" => [],
				];
				$data[$idx] = htmlspecialchars(_get('gclid'));
			}

			$email_list = array_map('trim', preg_split('#[;,]#', $form['email'], -1, PREG_SPLIT_NO_EMPTY));
			$mail_to = array();
			foreach ($email_list as $eml) {
				if (($m = is_mail($eml))) {
					$mail_to[] = $m;
				}
			}
			$mail_from = reset($mail_to);
			$mail_from_name = null;

			$fileSizeTotal = 0;
			$data = array();
			foreach ($fields as $fKey => $field) {
				$idx = $field['fidx'];
				if (isset($field['enabled']) && (!$field['enabled'])) continue;
				$fieldName = "wb_input_$idx";
				$required = isset($field["required"]) ? $field["required"] : ($field["type"] != "file");

				if (!$field['name'] && $field["type"] !== "checkbox" && $formSendType !== 'telegram') {
					$fields[$fKey]['name'] = SiteModule::__('Empty');
				}

				if ($field["type"] === "file") {
					if (!isset($_FILES[$fieldName]))
						continue;
					$err = null;
					foreach ($_FILES[$fieldName]["tmp_name"] as $fileIdx => $fileTmpName) {
						if (!$fileTmpName)
							continue;
						$fileName = $_FILES[$fieldName]["name"][$fileIdx];
						$fileSize = $_FILES[$fieldName]["size"][$fileIdx];
						$fileError = $_FILES[$fieldName]["error"][$fileIdx];
						$maxFileSizeTotalMB = isset($field["settings"]["fileMaxSize"]) ? intval($field["settings"]["fileMaxSize"]) : 0;
						if (!$maxFileSizeTotalMB)
							$maxFileSizeTotalMB = 2;
						$maxFileSizeTotal = $maxFileSizeTotalMB * 1024 * 1024;

						if ($fileSize > $maxFileSizeTotal || $fileError == UPLOAD_ERR_INI_SIZE || $fileError == UPLOAD_ERR_FORM_SIZE) {
							if (!$err)
								$err = "";
							$err .= sprintf(SiteModule::__('File %s is too big'), '"' . $fileName . '"') . "\n";
						} else if ($fileError != 0) {
							if (!$err)
								$err = "";
							$err .= sprintf(SiteModule::__('File %s could not be uploaded for sending'), '"' . $fileName . '"') . "\n";
						} else {
							$fileSizeTotal += $fileSize;
						}
					}
					if ($err) throw new ErrorException($err);
					// if( $fileSizeTotal > $maxFileSizeTotal ) {
					// throw new ErrorException(sprintf(SiteModule::__("Total size of attachments must not exceed %s MB"), $maxFileSizeTotalMB));
					// }
					if (!$fileSizeTotal && $required)
						$formErrors->required[] = $fieldName;
					if ($fileSizeTotal) @set_time_limit(180);
				} else if ($field["type"] == "hidden") {
					$data[$idx] = tr_($field['default']);
					if (isset($post[$fieldName])) {
						$data[$idx] = $post[$fieldName];
					}
				} else if ($field["type"] == "range") {
					$data[$idx] = array("from" => tr_($field['default']), "to" => tr_($field['default']));
					if (isset($post[$fieldName])) {
						$data[$idx] = $post[$fieldName];
					}
					if ((!$data[$idx] || empty($data[$idx]["from"]) || empty($data[$idx]["to"])) && $required)
						$formErrors->required[] = $fieldName;
				} else if ($field["type"] == "checkbox") {
					$options = isset($field["settings"]["options"]) ? $field["settings"]["options"] : array();
					foreach ($options as &$item) {
						$item = html_entity_decode((string)tr_($item));
					}
					unset($item);

					if (empty($post[$fieldName]) || count($options) == 1) {
						$fields[$fKey]['name'] = $fields[$fKey]['name'] ? $fields[$fKey]['name'] : $options[0];
						$data[$idx] = !empty($post[$fieldName]) ? true : false;
					} elseif (!isset($post[$fieldName])) {
						$data[$idx] = false;
					} elseif (is_array($post[$fieldName])) {
						$newValue = array();
						foreach ($post[$fieldName] as $item) {
							if (isset($options[$item])) {
								$newValue[] = $options[$item];
							}
						}
						$data[$idx] = $newValue;
					} else {
						$data[$idx] = true;
					}
					$fields[$fKey]['name'] = $fields[$fKey]['name'] ? $fields[$fKey]['name'] : SiteModule::__('Empty');

					if ((!$data[$idx] || empty($data[$idx])) && $required)
						$formErrors->required[] = $fieldName;
				} else if ($field["type"] == "radiobox") {
					if (!isset($post[$fieldName])) {
						if ($required)
							$formErrors->required[] = $fieldName;
						$data[$idx] = false;
					} else {
						$options = isset($field["settings"]["options"]) ? $field["settings"]["options"] : array();
						foreach ($options as &$item) {
							$item = html_entity_decode(tr_($item));
						}

						$data[$idx] = isset($options[$post[$fieldName]]) ? $options[$post[$fieldName]] : false;
					}
				} else {
					if (!isset($post[$fieldName])) {
						error_log("[Form error]: Field $fieldName is not present");
						throw new ErrorException($wb_form_sending_failed . " (6): " . sprintf(SiteModule::__('Field %s is not present'), $fieldName));
					}
					$max_len = ($field["type"] == "textarea") ? 65536 : 1024; // 65 kilobytes max for textarea and 1024 for other
					$valueRaw = $post[$fieldName];
					if (empty($valueRaw) && strlen($valueRaw) == 0 && $required) {
						if (!isset($formErrors->required)) $formErrors->required = array();
						$formErrors->required[] = $fieldName;
						$data[$idx] = $value = "";
					} else {
						$value = (strlen($valueRaw) > 0) ? substr(htmlspecialchars($valueRaw), 0, $max_len) : htmlspecialchars($valueRaw);
						if ($field["type"] == "select") {
							$options = isset($field["settings"]["options"]) ? $field["settings"]["options"] : array();
							$optIdx = array_search($valueRaw, $options);
							if ($optIdx === false && is_numeric($valueRaw) && isset($options[$valueRaw])) $optIdx = intval($valueRaw);
							if ($optIdx === false) $optIdx = 0;
							foreach ($options as &$item) {
								$item = html_entity_decode(tr_($item) ?: '');
							}
							$data[$idx] = trim($options[$optIdx]);
						} else
							$data[$idx] = $value;
					}
					if (($eml = is_mail($value))) $mail_from = $eml;
				}
			}

			if (isset($post['object']) && $post['object'])
				$data['object'] = $post['object'];

			$formErrors_t = (array)$formErrors;
			if (!empty($formErrors_t)) {
				throw new ErrorException($wb_form_sending_failed . ' (7)');
			}

			$attachmentsLogDir = dirname(__FILE__) . DIRECTORY_SEPARATOR . "forms_log_attachments";
			FormModule::logForm($attachmentsLogDir, $page_id, $post['wb_form_uuid'], $fields, $data);

			if ($formSendType == 'url' || $formSendType == 'telegram') {
				if (!class_exists('NetUtil')) {
					$netUtilFile = __DIR__ . '/src/NetUtil.php';
					if (is_file($netUtilFile)) require_once $netUtilFile;
				}
				if (!class_exists('NetUtil')) {
					throw new ErrorException($wb_form_sending_failed . ' (9)');
				}
			}

			if ($formSendType == 'url') {
				$postData = array();
				foreach ($fields as $idx => $field) {
					$fieldName = "wb_input_$idx";
					if ($field["type"] === "file") {
						if (!isset($_FILES[$fieldName]))
							continue;
						foreach ($_FILES[$fieldName]["tmp_name"] as $fileIdx => $fileTmpName) {
							if (!$fileTmpName)
								continue;
							$fileName = $_FILES[$fieldName]["name"][$fileIdx];
							$fileType = $_FILES[$fieldName]["type"][$fileIdx];
							if (class_exists('CURLFile')) {
								$postData["file_$fileIdx"] = new CURLFile($fileTmpName, $fileType, $fileName);
							} else {
								$postData["file_$fileIdx"] = '@' . $fileTmpName . ';filename=' . $fileName . ';type=' . $fileType;
							}
						}
					} elseif (is_array($data[$idx])) {
						$name = tr_($field["name"]);
						$value = $data[$idx];
						if ($field["name"] === '' && $field["type"] === 'checkbox') {
							$postData = array_merge($postData, array_fill_keys(array_values($value), true));
						} else {
							$postData[$name] = implode(',', $value);
						}
					} else {
						$name = tr_($field["name"]);
						$value = $data[$idx];
						$postData[$name] = $value;
					}
				}

				if ($apiPostUrl) {
					try {
						$resp = NetUtil::request($apiPostUrl, $postData, NetUtil::METHOD_POST, array('Content-type: multipart/form-data'),
							array(NetUtil::OPT_PARAMS_AS_ARRAY => true, NetUtil::OPT_IGNORE_STATUS_CODE => true));
						$error = null;
					} catch (ErrorException $ex) {
						$resp = null;
						$error = $ex->getMessage();
					}
					if (isset($resp->statusCode) && $resp->statusCode >= 200 && $resp->statusCode < 300) {
						$wb_form_send_state = empty($form['sentMessage']) ? 'Form was sent.' : tr_($form['sentMessage']);
						$wb_form_send_success = true;
					} else {
						$statusCode = $resp ? $resp->statusCode : 0;
						error_log('[Form sending error]: Failed to submit to URL: response code(' . $statusCode . ')' . ($error ? ': ' . $error : ''));
						throw new ErrorException($wb_form_sending_failed . ' (8)' . ($error ? ': ' . $error : ''));
					}
				}
				if ($webhookUrl) {
					if ($brandId) $postData['_brandId_'] = $brandId;
					$postData['_fromUrl_'] = getCurrUrl();
					try {
						$resp = NetUtil::request($apiPostUrl, $postData, NetUtil::METHOD_POST, array('Content-type: multipart/form-data'),
							array(NetUtil::OPT_PARAMS_AS_ARRAY => true, NetUtil::OPT_IGNORE_STATUS_CODE => true));
					} catch (ErrorException $ex) {
					}
				}
			} elseif ($formSendType == 'telegram') {
				$allowed_types = array('input', 'number', 'phone', 'email', 'textarea', 'checkbox', 'date', 'radiobox', 'select', 'hidden', 'range');

				$messageData = [];
				foreach ($fields as $idx => $field) {
					$name = '';
					$fieldName = "wb_input_$idx";
					if (in_array($field['type'], $allowed_types)) {
						if (isset($post[$fieldName]) || $field['type'] == 'checkbox') {
							if ($field['type'] == 'range') {
								$value = $post[$fieldName]['from'] . ' - ' . $post[$fieldName]['to'];
							} elseif ($field['type'] == 'checkbox') {
								if (empty($post[$fieldName]) || count($field['settings']['options']) == 1) {
									$name = !$field['name'] ? $field['settings']['options'][0] : '';
									$value = !empty($post[$fieldName]) ? SiteModule::__('Yes') : SiteModule::__('No');
								} else {
									$value = [];
									foreach ($post[$fieldName] as $val) {
										$value[] = SiteModule::__(tr_($field['settings']['options'][$val]));
									}
									$value = implode(', ', $value);
								}
							} elseif ($field['type'] == 'radiobox' || $field['type'] == 'select') {
								$options = array_map(function ($item) {
									return tr_($item);
								}, (isset($field['settings']['options']) && is_array($field['settings']['options'])) ? $field['settings']['options'] : []);
								$trval = in_array($post[$fieldName], $options) ? $post[$fieldName] : '';
								if (!is_string($trval)) $trval = '';
								$value = $trval;
							} elseif ($field['type'] == 'checkbox') {
								$value = "\n" . trim($post[$fieldName]);
							} else {
								$value = trim($post[$fieldName]);
							}
							$name = $name ? $name : (!$field['name'] ? SiteModule::__('Empty') : tr_($field['name']));
							$messageData[] = '<b>' . SiteModule::__(trim(strip_tags($name))) . ':</b>' . "\n" . $value;
						}
					}
				}

				$message = implode("\n", $messageData);

				$url = 'https://api.telegram.org/bot' . $telegramApiToken . '/sendMessage';
				$postData = array(
					'chat_id' => $telegramChatId,
					'text' => $message,
					'parse_mode' => 'HTML'
				);

				try {
					$resp = NetUtil::request($url, $postData, NetUtil::METHOD_POST, array('Content-type: multipart/form-data'),
						array(NetUtil::OPT_PARAMS_AS_ARRAY => true, NetUtil::OPT_IGNORE_STATUS_CODE => true));

					$body = json_decode($resp->body);
					if ($resp->statusCode != 200) {
						$error = $body->description;
						throw new ErrorException($error);
					} elseif (isset($body->ok) && $body->ok) {
						$wb_form_send_state = empty($form['sentMessage']) ? 'Form was sent.' : tr_($form['sentMessage']);
						$wb_form_send_success = true;
					}
				} catch (ErrorException $ex) {
					$error = $ex->getMessage();
					error_log("[Form telegram error]: {$error}");
					throw new ErrorException(SiteModule::__('Telegram error') . ': ' . $error);
				}

				if (count($_FILES)) {
					if (!file_exists($attachmentsDir)) {
						if (!mkdir($attachmentsDir, 0700)) {
							error_log('[Form error]: Failed to create a directory for attachments');
							throw new ErrorException($wb_form_sending_failed . ' (1): ' . SiteModule::__('Failed to create a directory for attachments'));
						}
					}

					foreach ($_FILES as $name => $file) {
						if (strpos($name, 'wb_input_') === false) {
							continue;
						}

						for ($i = 0; $i < count($file['name']); $i++) {

							if ($file['error'][$i] !== UPLOAD_ERR_OK) {
								continue;
							}

							$uploadedFilename = $attachmentsDir . DIRECTORY_SEPARATOR . basename($file['name'][$i]);
							move_uploaded_file($file['tmp_name'][$i], $uploadedFilename);

							if (strpos($file['type'][$i], 'image') !== false) {
								$url = 'https://api.telegram.org/bot' . $telegramApiToken . '/sendPhoto';
								$postData = array(
									'chat_id' => $telegramChatId,
									'photo' => new CURLFile($uploadedFilename, $file['type'][$i], $file['name'][$i])
								);
							} elseif (strpos($file['type'][$i], 'audio') !== false) {
								$url = 'https://api.telegram.org/bot' . $telegramApiToken . '/sendAudio';
								$postData = array(
									'chat_id' => $telegramChatId,
									'audio' => new CURLFile($uploadedFilename, $file['type'][$i], $file['name'][$i])
								);
							} elseif (strpos($file['type'][$i], 'video') !== false) {
								$url = 'https://api.telegram.org/bot' . $telegramApiToken . '/sendVideo';
								$postData = array(
									'chat_id' => $telegramChatId,
									'video' => new CURLFile($uploadedFilename, $file['type'][$i], $file['name'][$i])
								);
							} else {
								$url = 'https://api.telegram.org/bot' . $telegramApiToken . '/sendDocument';
								$postData = array(
									'chat_id' => $telegramChatId,
									'document' => new CURLFile($uploadedFilename, $file['type'][$i], $file['name'][$i])
								);
							}

							try {
								$resp = NetUtil::request($url, $postData, NetUtil::METHOD_POST, array('Content-type: multipart/form-data'),
									array(NetUtil::OPT_PARAMS_AS_ARRAY => true, NetUtil::OPT_IGNORE_STATUS_CODE => true));

								unlink($uploadedFilename);

								$body = json_decode($resp->body);
								if ($resp->statusCode != 200) {
									$error = $body->description;
									throw new ErrorException($error);
								}
							} catch (ErrorException $ex) {
								$error = $ex->getMessage();
								error_log("[Form telegram error]: {$error}");
							}
						}
					}
				}
			} else {
				if (!$mail_from) $mail_from = reset($mail_to);

				if (empty($mail_to)) {
					error_log('[Form configuration error]: receiver not specified');
					throw new ErrorException($wb_form_sending_failed . ' (5): ' . SiteModule::__('Receiver not specified'));
				}

				if ($siteInfo->disableFormSending) {
					//				throw new ErrorException(SiteModule::__('Form sending from preview is not available'));
				}
				requirePHPMailer();
				$mailer = new PHPMailer();
				$mailer->setLanguage(getPreferredLang());

				// cleanup old attachments that were not removed due to unknown reasons
				if (is_dir($attachmentsDir)) {
					$dir = opendir($attachmentsDir);
					if ($dir) {
						while ($f = readdir($dir)) {
							if ($f == "." || $f == ".." || $f == ".htaccess")
								continue;
							$fp = $attachmentsDir . DIRECTORY_SEPARATOR . $f;
							if (!is_file($fp))
								continue;
							if (filemtime($fp) < time() - 86400)
								unlink($fp);
						}
						closedir($dir);
					}
				}

				$movedFiles = array();
				foreach ($fields as $field) {
					$idx = $field['fidx'];
					$fieldName = "wb_input_$idx";
					if ($field["type"] === "file") {
						if (!isset($_FILES[$fieldName]))
							continue;
						if (!file_exists($attachmentsDir)) {
							if (!mkdir($attachmentsDir, 0700)) {
								error_log('[Form error]: Failed to create a directory for attachments');
								throw new ErrorException($wb_form_sending_failed . ' (1): ' . SiteModule::__('Failed to create a directory for attachments'));
							}
						}
						if (!is_dir($attachmentsDir)) {
							error_log('[Form error]: Attachments inode on the server is not a directory');
							throw new ErrorException($wb_form_sending_failed . ' (2): ' . SiteModule::__('Attachments inode on the server is not a directory'));
						}
						foreach ($_FILES[$fieldName]["tmp_name"] as $fileIdx => $fileTmpName) {
							if (!$fileTmpName)
								continue;
							$fileName = $_FILES[$fieldName]["name"][$fileIdx];
							$tmpCopyName = $attachmentsDir . DIRECTORY_SEPARATOR . basename($fileTmpName);
							if (!move_uploaded_file($fileTmpName, $tmpCopyName)) {
								foreach ($movedFiles as $tmpCopyName)
									unlink($tmpCopyName);
								error_log('[Form error]: Failed to move uploaded file to attachments directory');
								throw new ErrorException($wb_form_sending_failed . ' (3): ' . SiteModule::__('Failed to move uploaded file to attachments directory'));
							}
							$movedFiles[] = $tmpCopyName;
							$secureFileName = $fileName;
							$secureFileName = preg_replace("#[\\\\/<>\\?;:,=]+#isu", "_", $secureFileName);
							$secureFileName = preg_replace("#\\.\\.+#isu", ".", $secureFileName);
							$mailer->addAttachment($tmpCopyName, $secureFileName, "base64");
						}
					}
				}

				if (isset($form['smtpEnable']) && $form['smtpEnable'] && isset($form['smtpHost']) && $form['smtpHost']) {
					/* $mailer->Debugoutput = function($string) {
						file_put_contents(__DIR__.'/smtp-debug.log', $string."\n", FILE_APPEND);
					};
					$mailer->SMTPDebug = 4; */
					$mailer->isSMTP();
					$mailer->Host = ((isset($form['smtpHost']) && $form['smtpHost']) ? $form['smtpHost'] : 'localhost');
					$mailer->Port = ((isset($form['smtpPort']) && intval($form['smtpPort'])) ? intval($form['smtpPort']) : 25);
					$mailer->SMTPSecure = ((isset($form['smtpEncryption']) && $form['smtpEncryption']) ? $form['smtpEncryption'] : '');
					$mailer->SMTPAutoTLS = false;
					if (isset($form['smtpUsername']) && $form['smtpUsername'] && isset($form['smtpPassword']) && $form['smtpPassword']) {
						$mailer->SMTPAuth = true;
						$mailer->Username = ((isset($form['smtpUsername']) && $form['smtpUsername']) ? $form['smtpUsername'] : '');
						$mailer->Password = ((isset($form['smtpPassword']) && $form['smtpPassword']) ? $form['smtpPassword'] : '');
					}
					$mailer->SMTPOptions = array('ssl' => array(
						'verify_peer' => false,
						'verify_peer_name' => false,
						'allow_self_signed' => true
					));
				}

				$style = "* { font: 12px Arial; }\nstrong { font-weight: bold; }";

				$toHasGmail = false;
				foreach ($mail_to as $eml) {
					if (strpos($eml, 'gmail.com') !== false) $toHasGmail = true;
					$mailer->AddAddress($eml);
				}

				$sender_email = (isset($form['emailFrom']) && $form['emailFrom']) ? trim($form['emailFrom']) : ('no-reply@' . $siteInfo->domain);
				$sender_name = $mail_from_name;
				if (preg_match('#^([^<]+|)<([^>]+)>$#', $sender_email, $m)) {
					if (trim($m[1])) $sender_name = trim($m[1]);
					$sender_email = trim($m[2]);
				} else if (preg_match('#^<([^>]+)>(.+|)$#', $sender_email, $m)) {
					if (trim($m[2])) $sender_name = trim($m[2]);
					$sender_email = trim($m[1]);
				}
				$mailer->SetFrom($sender_email, ($sender_name ?: ''));
				if (strpos($mail_from, 'gmail.com') === false || !$toHasGmail) {
					// do not add "Reply-To" header if both Receiver and ReplyTo are Gmail
					// form sending fails in such case.
					$mailer->addReplyTo($mail_from, $mail_from_name ? $mail_from_name : '');
				}

				$mailer->CharSet = 'utf-8';
				$message = '';
				if (isset($form['object']) && $form['object']) {
					if (isset($form['objectRenderer']) && $form['objectRenderer'] && is_callable($form['objectRenderer'])) {
						$objectStr = call_user_func((strpos($form['objectRenderer'], '::') ? explode('::', $form['objectRenderer']) : $form['objectRenderer']), $form, $data);
					} else {
						$objectStr = '<p><strong>' . htmlspecialchars($form['object']) . '</strong></p>';
					}
					if ($objectStr) $message .= $objectStr;
				}
				$message .= '<table cellspacing="0" cellpadding="5">';
				foreach ($fields as $idx => $field) {
					if ($field["type"] === "file")
						continue;
					$name = tr_($field["name"]);
					$value = $data[$idx];
					$escapeName = function ($name) {
						return trim(strip_tags($name));
					};
					$escapeVal = function ($value) {
						if (is_array($value)) $value = implode(PHP_EOL, $value);
						return trim(nl2br($value));
					};
					$td = function ($content) {
						return '<td style="vertical-align: top;">' . $content . '</td>';
					};
					$message .= "<tr>" . $td("<strong>{$escapeName($name)}: </strong>");
					if ($field["type"] == "textarea")
						$message .= $td('<div style="max-width: 400px;">' . $escapeVal($value) . '</div>') . "</tr>\n";
					else if ($field["type"] == "checkbox") {
						if (is_array($value)) {
							$message .= $td($escapeVal($value)) . "</tr>\n";
						} else {
							$message .= $td($value ? tr_('Yes') : tr_('No')) . "</tr>\n";
						}
					} else if ($field["type"] == "range") {
						$message .= $td($escapeVal($value["from"]) . ' - ' . $escapeVal($value["to"])) . "</tr>\n";
					} else
						$message .= $td($escapeVal($value)) . "</tr>\n";
					$message .= "</tr>\n";
				}
				$message .= '</table>';
				// echo $message; exit;

				$html =
					'<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0 Transitional//EN">
		<html>
			<head>
				<title>' . $form["subject"] . '</title>
				<meta http-equiv=Content-Type content="text/html; charset=utf-8">
				' . ($style ? "<style><!--\n$style\n--></style>\n\t\t" : "") . '</head>
			<body>' . $message . '</body>
		</html>';
				$mailer->MsgHTML($html);
				$mailer->AltBody = preg_replace('/[\r\n]{3,9}/', "\n\n", str_replace('&nbsp;', '', strip_tags(str_replace("</tr>", "</tr>\n", $message))));
				$mailer->Subject = $form["subject"];
				ob_start();
				$res = $mailer->Send();
				$wb_form_send_success = $res;
				ob_get_clean();
				if ($res) {
					$wb_form_send_state = empty($form['sentMessage']) ? '' : tr_($form['sentMessage']);
				} else {
					if ($mailer->ErrorInfo) error_log('[Form sending error]: ' . $mailer->ErrorInfo);
					throw new ErrorException($wb_form_sending_failed . ' (4): ' . $mailer->ErrorInfo);
				}
				if (isset($form['loggingHandler']) && $form['loggingHandler'] && is_callable($form['loggingHandler'])) {
					call_user_func((strpos($form['loggingHandler'], '::') ? explode('::', $form['loggingHandler']) : $form['loggingHandler']), $form, $data, $res);
				}
				foreach ($movedFiles as $tmpCopyName)
					unlink($tmpCopyName);
			}
		} catch (ErrorException $ex) {
			if (!$wb_form_send_state) {
				$wb_form_send_state = $ex->getMessage();
				$formErrors->any = true; // set values to fields back in case of error
			}
			$wb_form_send_success = false;
		}
	} else {
		$formErrors = new stdClass();
		$wb_form_reaccept_cookie = false;
		$wb_form_send_state = false;
		$wb_form_send_success = false;
		$wb_form_id = $post['wb_form_id'];
		$wb_form_popup_mode = (isset($post['wb_popup_mode']) && $post['wb_popup_mode'] == 1);
		$wb_target_origin = getOrigin();

		$wb_form_send_state = SiteModule::__('There was a problem submitting your form. This can happen when you leave a page open for a long time. Please refresh and try again.');
		$formErrors->any = true; // set values to fields back in case of error
		$wb_form_send_success = false;
	}

	if (session_id()) {
		$_SESSION['post'] = $post;
		$_SESSION['formErrors'] = $formErrors;
		$_SESSION['wb_form_id'] = $wb_form_id;
		$_SESSION['wb_form_send_success'] = $wb_form_send_success;
		$_SESSION['wb_form_popup_mode'] = $wb_form_popup_mode;
		$_SESSION['wb_target_origin'] = $wb_target_origin;
		$_SESSION['wb_form_send_state'] = $wb_form_send_state;
		$_SESSION['wb_form_reaccept_cookie'] = $wb_form_reaccept_cookie;
		if ($wb_form_send_success) {
			if ( isset($form['redirectUrl']) && !is_null($form['redirectUrl'])) {
				$redirectUrl = tr_($form['redirectUrl']);
				if ($redirectUrl == '{{base_url}}') {
					$url = getBaseUrl();
				} else if (is_string($redirectUrl) && preg_match('#^https?://#i', $redirectUrl)) {
					$url = $redirectUrl;
				} elseif (is_string($redirectUrl) && preg_match('#^wb_popup:#i', $redirectUrl)) {
					$parseUrl = parse_url(getCurrUrl());
					$parseUrl['query'] = (isset($parseUrl['query']) ? $parseUrl['query'] : '') . '&wbPopupOpen=' . urlencode($redirectUrl);
					$parseUrl['query'] = ltrim($parseUrl['query'], '&');
					$url = unparse_url($parseUrl);
//					$url .= '?wbPopupOpen=' . urlencode($redirectUrl);
					$popupQuery = 'wbPopupOpen=' . urlencode($redirectUrl);
				} else {
					$url = getBaseUrl() . $redirectUrl;
				}
				if (!is_null(_get('wbPopupMode')) && (int)_get('wbPopupMode') == 1) {
					if (isset($popupQuery)) {
						// @note: when we have popup with form and redirecting to another popup then need set "wbPopupOpen" for parent location
						// else we redirecting to popup page without popup
						echo '<script> window.parent.location.search = (window.parent.location.search.length ? (window.parent.location.search + "&") : "?") + ' . json_encode($popupQuery) . '; </script>';
					} else {
						echo '<script> window.parent.location.href = ' . json_encode($url) . '; </script>';
					}
					exit();
				} else {
					header('Location: ' . $url);
				}
			} else if (!is_null(_get('wbPopupMode')) && (int)_get('wbPopupMode') == 1) {
				echo '<script> window.parent.location.reload(); </script>';
				exit();
			} else {
				header('Location: '.getCurrUrl());
			}
		} else {
			header('Location: '.getCurrUrl());
		}
		exit();
	}
}

/**
 * Load PHPMailer library.
 * @param bool $noErrorException
 * @return bool true if PHPMailer loaded successfully, and false if not.
 * @throws ErrorException
 */
function requirePHPMailer($noErrorException = false) {
	if (version_compare(phpversion(), '5.5') < 0) {
		if (!$noErrorException) throw new ErrorException('Your PHP version is outdated for sending mails. Please update PHP version to 5.6 or higher.');
		return false;
	}
	if (!class_exists('\PHPMailer\PHPMailer\PHPMailer')) {
		require_once dirname(__FILE__).'/phpmailer/Exception.php';
		require_once dirname(__FILE__).'/phpmailer/OAuth.php';
		require_once dirname(__FILE__).'/phpmailer/PHPMailer.php';
		require_once dirname(__FILE__).'/phpmailer/POP3.php';
		require_once dirname(__FILE__).'/phpmailer/SMTP.php';

		// in PHP 7.4 validation of cyrilic email address does not work
		// due to unknown reason. So we just ignore PHPMailer validation.
		if (version_compare(phpversion(), '7.4') >= 0) {
			\PHPMailer\PHPMailer\PHPMailer::$validator = function($address) { return true; };
		}
	}
	return true;
}

function is_mail($mail) {
	if (preg_match("/^[0-9a-zA-ZА-Яа-я\.\-\_\w]+\@[0-9a-zA-ZА-Яа-я\.\-\_\w]+\.[0-9a-zA-ZА-Яа-я\.\-\_\w]+$/isu", trim($mail)))
		return trim($mail);
	return "";
}

function mini_text($text) {
	return trim(substr(strip_tags($text), 0, 100), " \n\r\t\0\x0B.").'...';
}

function _http_get($url, $post_vars = false) {
	$post_contents = '';
	if ($post_vars) {
		if (is_array($post_vars)) {
			foreach($post_vars as $key => $val) {
				$post_contents .= ($post_contents ? '&' : '').urlencode($key).'='.urlencode($val);
			}
		} else {
			$post_contents = $post_vars;
		}
	}

	$uinf = parse_url($url);
	$host = $uinf['host'];
	$path = $uinf['path'];
	$path .= (isset($uinf['query']) && $uinf['query']) ? ('?'.$uinf['query']) : '';
	$headers = array(
		($post_contents ? 'POST' : 'GET')." $path HTTP/1.1",
		"Host: $host",
	);
	if ($post_contents) {
		$headers[] = 'Content-Type: application/x-www-form-urlencoded';
		$headers[] = 'Content-Length: '.strlen($post_contents);
	}

	$ch = curl_init();
	curl_setopt($ch, CURLOPT_SSL_VERIFYHOST, 0);
	curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, 0);
	curl_setopt($ch, CURLOPT_URL,$url);
	curl_setopt($ch, CURLOPT_RETURNTRANSFER, 1);
	curl_setopt($ch, CURLOPT_TIMEOUT, 600);
	curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);

	if ($post_contents) {
		curl_setopt($ch, CURLOPT_POST, 1);
		curl_setopt($ch, CURLOPT_POSTFIELDS, $post_contents);
	}

	$data = curl_exec($ch);
	if (curl_errno($ch)) {
		return false;
	}
	curl_close($ch);

	return $data;
}

function unparse_url($parsed_url) {
	$scheme   = isset($parsed_url['scheme']) ? $parsed_url['scheme'] . '://' : '';
	$host     = isset($parsed_url['host']) ? $parsed_url['host'] : '';
	$port     = isset($parsed_url['port']) ? ':' . $parsed_url['port'] : '';
	$user     = isset($parsed_url['user']) ? $parsed_url['user'] : '';
	$pass     = isset($parsed_url['pass']) ? ':' . $parsed_url['pass']  : '';
	$pass     = ($user || $pass) ? "$pass@" : '';
	$path     = isset($parsed_url['path']) ? $parsed_url['path'] : '';
	$query    = isset($parsed_url['query']) ? '?' . $parsed_url['query'] : '';
	$fragment = isset($parsed_url['fragment']) ? '#' . $parsed_url['fragment'] : '';
	return "$scheme$user$pass$host$port$path$query$fragment";

}

function simplifyText($text) {
	$mb = function_exists('mb_strtolower');
	$textLen = ($mb ? mb_strlen($text) : strlen($text));
	$textLow = ($mb ? mb_strtolower($text) : strtolower($text));
//		$res = @iconv('utf-8', 'cp1252//TRANSLIT//IGNORE', $textLow);
	$res = translitToLatin($textLow);
	$resLen = ($mb ? mb_strlen($res) : strlen($res));
	return ($resLen/2 < $textLen) ? $textLow : $res;
}

/**
 * Transliterate text to latin.
 * @param string $text text to transliterate.
 * @return string
 */
function translitToLatin($text) {
	// transliterate cyrillic chars
	$cyrillic = array('а','б','в','г','д','е', 'ё', 'ж','з','и','й','к','л','м','н','о','п','р','с','т','у','ф','х','ц', 'ч', 'ш',   'щ','ъ','ы','ь', 'э', 'ю', 'я','А','Б','В','Г','Д','Е', 'Ё', 'Ж','З','И','Й','К','Л','М','Н','О','П','Р','С','Т','У','Ф','Х','Ц', 'Ч', 'Ш',   'Щ','Ъ','Ы','Ь', 'Э', 'Ю', 'Я');
	$latinCr =  array('a','b','v','g','d','e','yo','zh','z','i','j','k','l','m','n','o','p','r','s','t','u','f','h','c','ch','sh','shch', '','y', '','eh','yu','ya','A','B','V','G','D','E','Yo','Zh','Z','I','J','K','L','M','N','O','P','R','S','T','U','F','H','C','Ch','Sh','Shch', '','Y', '','Eh','Yu','Ya');
	$textNoCr = str_replace($cyrillic, $latinCr, $text);
	// transliterate lithuanian chars
	$lithuanian = array('ą','Ą','č','Č','ę','Ę','ė','Ė','į','Į','š','Š','ų','Ų','ū','Ū','ž','Ž');
	$latinLt =    array('a','A','c','C','e','E','e','E','i','I','s','S','u','U','u','U','z','Z');
	$textNoLt = str_replace($lithuanian, $latinLt, $textNoCr);
	$accents = array(
		'à' => 'a', 'ô' => 'o', 'ď' => 'd', 'ë' => 'e', 'ơ' => 'o',
		'ß' => 'ss', 'ă' => 'a', 'ř' => 'r', 'ț' => 't', 'ň' => 'n', 'ā' => 'a', 'ķ' => 'k',
		'ŝ' => 's', 'ỳ' => 'y', 'ņ' => 'n', 'ĺ' => 'l', 'ħ' => 'h', 'ó' => 'o',
		'ú' => 'u', 'ě' => 'e', 'é' => 'e', 'ç' => 'c', 'ẁ' => 'w', 'ċ' => 'c', 'õ' => 'o',
		'ø' => 'o', 'ģ' => 'g', 'ŧ' => 't', 'ș' => 's', 'ĉ' => 'c',
		'ś' => 's', 'î' => 'i', 'ű' => 'u', 'ć' => 'c', 'ŵ' => 'w',
		'ö' => 'oe', 'è' => 'e', 'ŷ' => 'y', 'ł' => 'l',
		'ů' => 'u', 'ş' => 's', 'ğ' => 'g', 'ļ' => 'l', 'ƒ' => 'f',
		'ẃ' => 'w', 'å' => 'a', 'ì' => 'i', 'ï' => 'i', 'ť' => 't',
		'ŗ' => 'r', 'ä' => 'ae', 'í' => 'i', 'ŕ' => 'r', 'ê' => 'e', 'ü' => 'ue', 'ò' => 'o',
		'ē' => 'e', 'ñ' => 'n', 'ń' => 'n', 'ĥ' => 'h', 'ĝ' => 'g', 'đ' => 'd', 'ĵ' => 'j',
		'ÿ' => 'y', 'ũ' => 'u', 'ŭ' => 'u', 'ư' => 'u', 'ţ' => 't', 'ý' => 'y', 'ő' => 'o',
		'â' => 'a', 'ľ' => 'l', 'ẅ' => 'w', 'ż' => 'z', 'ī' => 'i', 'ã' => 'a', 'ġ' => 'g',
		'ō' => 'o', 'ĩ' => 'i', 'ù' => 'u', 'ź' => 'z', 'á' => 'a',
		'û' => 'u', 'þ' => 'th', 'ð' => 'dh', 'æ' => 'ae', 'µ' => 'u', 'ĕ' => 'e',

		'Ә' => 'A','ә' => 'a', 'Ғ' => 'G','ғ' => 'g', 'Қ' => 'K','қ' => 'k',
		'Ң' => 'N','ң' => 'n', 'Ө' => 'O','ө' => 'o', 'Ұ' => 'U','ұ' => 'u',
		'Ү' => 'U','ү' => 'u', 'І' => 'Y','і' => 'y', 'Һ' => 'H','һ' => 'h',


		'À' => 'a', 'Ô' => 'o', 'Ď' => 'd', 'Ë' => 'e', 'Ơ' => 'o',
		'ß' => 'ss','Ă' => 'a', 'Ř' => 'r', 'Ț' => 't', 'Ň' => 'n', 'Ā' => 'a', 'Ķ' => 'k',
		'Ŝ' => 's', 'Ỳ' => 'y', 'Ņ' => 'n', 'Ĺ' => 'l', 'Ħ' => 'h', 'Ó' => 'o',
		'Ú' => 'u', 'Ě' => 'e', 'É' => 'e', 'Ç' => 'c', 'Ẁ' => 'w', 'Ċ' => 'c', 'Õ' => 'o',
		'Ø' => 'o', 'Ģ' => 'g', 'Ŧ' => 't', 'Ș' => 's', 'Ĉ' => 'c',
		'Ś' => 's', 'Î' => 'i', 'Ű' => 'u', 'Ć' => 'c', 'Ŵ' => 'w',
		'Ö' => 'oe', 'Ŷ' => 'y', 'Ł' => 'l',
		'Ů' => 'u', 'Ş' => 's', 'Ğ' => 'g', 'Ļ' => 'l', 'Ƒ' => 'f',
		'Ẃ' => 'w', 'Å' => 'a', 'Ì' => 'i', 'Ï' => 'i', 'Ť' => 't',
		'Ŗ' => 'r', 'Ä' => 'ae','Í' => 'i', 'Ŕ' => 'r', 'Ê' => 'e', 'Ü' => 'ue', 'Ò' => 'o',
		'Ē' => 'e', 'Ñ' => 'n', 'Ń' => 'n', 'Ĥ' => 'h', 'Ĝ' => 'g', 'Đ' => 'd', 'Ĵ' => 'j',
		'Ÿ' => 'y', 'Ũ' => 'u', 'Ŭ' => 'u', 'Ư' => 'u', 'Ţ' => 't', 'Ý' => 'y', 'Ő' => 'o',
		'Â' => 'a', 'Ľ' => 'l', 'Ẅ' => 'w', 'Ż' => 'z', 'Ī' => 'i', 'Ã' => 'a', 'Ġ' => 'g',
		'Ō' => 'o', 'Ĩ' => 'i', 'Ù' => 'u', 'Ź' => 'z', 'Á' => 'a',
		'Û' => 'u', 'Þ' => 'th','Ð' => 'dh', 'Æ' => 'ae',			 'Ĕ' => 'e'
	);
	$textLatinN = str_replace(array_keys($accents), array_values($accents), $textNoLt);
	// transliterate other language chars
	$textLatin = function_exists("iconv") ? @iconv('UTF-8', 'ISO-8859-1//TRANSLIT//IGNORE', $textLatinN) : $textLatinN;
	return $textLatin;
}

function checkSiteRedirects(SiteInfo $siteInfo, SiteRequestInfo $requestInfo, array $redirectItems) {
	if (!count($redirectItems)) {
		return;
	}

	$baseUrl = getBaseUrl();
	$currUri = ltrim($requestInfo->requestUri, '/');
	$currQs = _get();

	$defLang = ($siteInfo->defLang ? $siteInfo->defLang : null);

	$hasMbstring = function_exists('mb_strpos');

	$matches = [];
	foreach ($redirectItems as $item) {
		$item = (array)$item;
		if (!$item['enabled']) {
			continue;
		}
		$fromUriRaw = ltrim(trim($item['fromUrl'], " \n\r\t\v\0'\""), '/');
		$pp = explode('?', $fromUriRaw, 2);
		$fromUri = $pp[0];
		$fromQs = [];
		if (isset($pp[1]) && $pp[1]) {
			parse_str($pp[1], $fromQs);
		}
		$partialMatch = ($hasMbstring && mb_strpos($currUri, $fromUri) === 0
				|| !$hasMbstring && strpos($currUri, $fromUri) === 0);
		$exactMatch = rtrim($currUri, '/') == rtrim($fromUri, '/');
		$exact = $item['exact'];
		if (!$partialMatch || ($exact && !$exactMatch)) {
			continue;
		}

		$to = (array)$item['toUrl'];
		$toUrl = $to['url'];
		$toType = $to['type'];
		$toAnchor = (isset($to['anchor']) && is_string($to['anchor'])) ? $to['anchor'] : '';
		$toQs = array_merge_recursive($currQs, $fromQs);

		$redirUrl = null;
		if ($toType == 'page') {
			$pageUri = getPageUri($toUrl, $defLang, $siteInfo);
			$redirUrl = $baseUrl . $pageUri
				.(empty($toQs) ? '' : '?'.http_build_query($toQs))
				.($toAnchor ? "#{$toAnchor}" : '');
		}
		else if ($toType == 'url') {
			$redirUrl = $toUrl;
		}
		else if ($toType == 'file') {
			$redirUrl = preg_match('#^https?:\/\/#i', $toUrl)
				? $toUrl
				: $baseUrl . '/' . ltrim($toUrl, '/');
		}
		if ($redirUrl) $matches[$fromUri] = $redirUrl;
	}
	if (empty($matches)) {
		return;
	}

	uksort($matches, function($a, $b) use($hasMbstring) {
		$al = $hasMbstring ? mb_strlen($a) : strlen($a);
		$bl = $hasMbstring ? mb_strlen($b) : strlen($b);
		if ($al == $bl) return 0;
		return $al > $bl ? -1 : 1;
	});
	$url = reset($matches);

	if ($url && $url != getCurrUrl()) {
		header('Location: '. $url, true, 301);
		exit();
	}
}

function isSitemapUrl(SiteRequestInfo $requestInfo)
{
	return  in_array(trim($requestInfo->requestUri, '/'), array('sitemap.xml', 'sitemap-alt.xml'));
}

function genSitemap()
{
	$file = __DIR__.'/sitemap_template';
	$xml = is_file($file) ? file_get_contents($file) : '';
	if ($xml) {
		$xml = str_replace('{{base_url}}', getBaseUrl(), $xml);
		header('Content-Type: application/xml; charset=UTF-8');
		echo $xml;
		exit();
	}
}

class GetHelper {
	private static $get = null;

	public static function init($data) {
		self::$get = $data;
	}

	public static function set($key, $val) {
		if (self::$get === null) {
			self::$get = [];
		}
		self::$get[$key] = $val;
	}

	public static function getGet() {
		return self::$get;
	}
}

function _get($key = null) {
	if (GetHelper::getGet() === null) {
		GetHelper::init([]);
		if (empty($_GET) && isset($_SERVER['REQUEST_URI'])) {
			$uri_parts = explode('?', $_SERVER['REQUEST_URI'], 2);
			if (isset($uri_parts[1]) && $uri_parts[1] !== '') {
				parse_str($uri_parts[1], $get_params);
				foreach ($get_params as $k => $v) {
					GetHelper::set($k, $v);
				}
			}
		}
		else {
			GetHelper::init($_GET);
		}
	}
	$data = GetHelper::getGet();

	return !$key ? $data : (isset($data[$key]) ? $data[$key] : null);
}

function replaceLangAlternates(\SiteInfo $siteInfo, &$out, array $langs, $pageId) {
	$storeItem = class_exists('StoreModule') ? StoreModule::resolveItemByRequest(StoreModule::$storeNav) : null;
	$blogItem = class_exists('BlogModule') ? BlogModule::resolveItemByRequest(BlogModule::$blogNav) : null;
	foreach ($langs as $ln => $default) {
		$pageUri = getPageUri($pageId, $ln, $siteInfo);
		if ($storeItem && isset($storeItem->alias) && isset($storeItem->alias->$ln)) {
			$pageUri = rtrim($pageUri, '/') .'/'. $storeItem->alias->$ln . ($siteInfo->useTrailingSlashes ? '/' : '');
		}
		elseif ($blogItem && isset($blogItem->alias) && isset($blogItem->alias->$ln)) {
			$pageUri = rtrim($pageUri, '/') .'/'. $blogItem->alias->$ln . ($siteInfo->useTrailingSlashes ? '/' : '');
		}
		$out = str_replace('{{lang_'.$ln.'}}', $pageUri, $out);
		$out = str_replace(urlencode('{{lang_'.$ln.'}}'), $pageUri, $out);
	}
}
