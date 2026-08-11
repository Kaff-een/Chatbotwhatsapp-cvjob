from chatbot_graph import build_search_reply

def test_build_search_reply():
    print("Running unit tests on build_search_reply...")

    # Case 1: Job search
    tool_calls_job = [
        ("search_job_offers", "https://www.cvjob.org/offres-emploi?search=python&location=casablanca")
    ]
    reply = build_search_reply(
        tool_calls=tool_calls_job,
        language="fr",
        name="Jean",
        used_cv=False
    )
    print(f"Job search result: {reply}")
    assert reply == "https://www.cvjob.org/offres-emploi?search=python&location=casablanca", f"Failed, got: {reply}"

    # Case 2: Internship search
    tool_calls_internship = [
        ("search_internship_offers", "https://www.cvjob.org/offres-stage?search=marketing&location=rabat")
    ]
    reply = build_search_reply(
        tool_calls=tool_calls_internship,
        language="fr",
        name="Jean",
        used_cv=True
    )
    print(f"Internship search result: {reply}")
    assert reply == "https://www.cvjob.org/offres-stage?search=marketing&location=rabat", f"Failed, got: {reply}"

    # Case 3: Mixed tool calls (reversed order, should get the last successful one)
    tool_calls_mixed = [
        ("get_candidate_cv", "some cv text"),
        ("search_job_offers", "https://www.cvjob.org/offres-emploi?search=devops")
    ]
    reply = build_search_reply(
        tool_calls=tool_calls_mixed,
        language="en",
        name="Alice",
        used_cv=True
    )
    print(f"Mixed tools result: {reply}")
    assert reply == "https://www.cvjob.org/offres-emploi?search=devops", f"Failed, got: {reply}"

    # Case 4: No matching tool call
    tool_calls_none = [
        ("get_candidate_cv", "some cv text")
    ]
    reply = build_search_reply(
        tool_calls=tool_calls_none,
        language="fr",
        name="Jean",
        used_cv=False
    )
    print(f"No match result: {reply}")
    assert reply is None, f"Failed, got: {reply}"

    print("ALL UNIT TESTS PASSED SUCCESSFULLY! The function returns exactly the raw URL preserving its structure.")

if __name__ == "__main__":
    test_build_search_reply()
