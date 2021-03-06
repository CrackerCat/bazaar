import dexofuzzy

from django.conf import settings
from elasticsearch import Elasticsearch

def transform_results(results):
    return [doc['_source'] for doc in results['hits']['hits']]


def transform_hl_results(results):
    ret = []
    for doc in results['hits']['hits']:
        d = {}
        for k, v in doc.items():
            if k.startswith('_'):
                k = k[1:]
            d[k] = v
        ret.append(d)
    return ret


def append_dexofuzzy_similarity(results, key, top_n=5):
    """
    Add dexofuzzy similarity info into a transformed result dict
    :param results: transformed result dict
    :param key: the key to append
    :param top_n: add only the n most similar results
    :return: the modified results dict
    """
    if len(results) > 50:
        return results

    for r in results:
        matches = []
        for sample in results:
            try:
                if r['source']['sha256'] != sample['source']['sha256']:
                    sim = dexofuzzy.compare(r['source']['dexofuzzy']['apk'], sample['source']['dexofuzzy']['apk'])
                    if sim > 0:
                        matches.append(
                            {'score': sim, 'sha256': sample['source']['sha256'], 'handle': sample['source']['handle']})
            except Exception as e:
                pass

        matches = sorted(matches, key=lambda ele: ele['score'], reverse=True)
        limit = min(len(matches), top_n)
        r[key] = matches[:limit]

    return results


def get_similarity_matrix(results):
    matrix = []
    for r in results:
        for s in r['sim']:
            matrix.append({
                'a': r['source']['sha256'],
                'b': s['sha256'],
                'score': s['score'],
            })

    return matrix


def get_aggregations(results):
    aggregations = {}
    result_count = results['hits']['total']['value']
    mapping = {
        'permissions': 'Requested permissions',
        'domains': 'Found domains',
        'android_api': 'Called Android API',
        'android_features': 'Requested Android features',
    }

    for k, v in results['aggregations'].items():
        for b in v['buckets']:
            b['doc_count'] = 100. * (b['doc_count'] / result_count)
        aggregations[k] = {
            'key': k,
            'title': mapping[k],
            'buckets': v['buckets']
        }

    return aggregations


def init_es():

    index_settings = {
        'settings': {
            'index': {
                'mapping': {
                    'total_fields': {
                        'limit': '65635'
                    }
                },
                'highlight': {
                    'max_analyzed_offset': '60000000'
                }
            }
        },
        "mappings": {
            "properties": {
                "java_classes": {
                    "type": "text",
                    "term_vector": "with_positions_offsets"
                },
                "analysis_date": {
                    "type": "date"
                }
            }
        }
    }

    index_mappings = {
        "properties": {
            "java_classes": {
                "type": "keyword",
                "term_vector": "with_positions_offsets"
            },
            "analysis_date": {
                "type": "date"
            }
        }
    }

    es = Elasticsearch([settings.ELASTICSEARCH_HOST])
    try:
        es.indices.create(index=settings.ELASTICSEARCH_GP_INDEX)
        es.indices.create(index=settings.ELASTICSEARCH_TASKS_INDEX)
        es.indices.create(index=settings.ELASTICSEARCH_APK_INDEX, body=index_settings)
    except Exception as e:
        print(e)
        pass
